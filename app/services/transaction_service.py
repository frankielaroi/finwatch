import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (get_ml_alert_threshold, get_ml_rule_weight,
                             get_ml_score_weight)
from app.metrics.prometheus import SCORING_FAILURES
from app.ml.scorer import score_transaction as score_txn
from app.models.alert import Alert
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.services import entity_service as _entity_service
from app.services.monitoring_service import record_scoring_failure


def generate_txn_id() -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    uid = str(uuid.uuid4().int)[:5]
    return f"TXN-{date_str}-{uid.zfill(5)}"


# --- Rules Engine ---
HIGH_RISK_COUNTRIES = {"IR", "KP", "SY", "CU", "VE", "MM", "AF", "LY", "SO", "YE"}
CTR_THRESHOLD = 10000.0
STRUCTURING_LOWER = 9000.0


def run_rules(txn: TransactionCreate) -> tuple[list[str], float]:
    """Run rules engine. Returns (flag_reasons, risk_score_contribution)."""
    flags = []
    score = 0.0

    # Rule 1: CTR threshold
    if txn.amount >= CTR_THRESHOLD and txn.txn_type == "cash_deposit":
        flags.append("CTR_THRESHOLD")
        score += 30

    # Rule 2: Structuring (just below $10K)
    if (
        STRUCTURING_LOWER <= txn.amount < CTR_THRESHOLD
        and txn.txn_type == "cash_deposit"
    ):
        flags.append("STRUCTURING_PATTERN")
        score += 40

    # Rule 3: High risk jurisdiction
    if txn.counterparty_country in HIGH_RISK_COUNTRIES:
        flags.append("HIGH_RISK_JURISDICTION")
        score += 35

    # Rule 4: Round number bias
    if txn.amount % 1000 == 0 and txn.amount >= 5000:
        flags.append("ROUND_NUMBER_BIAS")
        score += 10

    # Rule 5: Large wire out
    if txn.txn_type == "wire_out" and txn.amount >= 50000:
        flags.append("LARGE_WIRE_OUT")
        score += 25

    # Rule 6: No counterparty info on large transaction
    if txn.amount >= 5000 and not txn.counterparty_name:
        flags.append("MISSING_COUNTERPARTY")
        score += 15

    return flags, min(score, 100.0)


def get_ensemble_score(rule_score: float, ml_score: float) -> float:
    return (rule_score * get_ml_rule_weight()) + (
        ml_score * 100.0 * get_ml_score_weight()
    )


def should_generate_alert(ensemble_score: float, is_flagged: bool) -> bool:
    return is_flagged or ensemble_score >= get_ml_alert_threshold()


def _canonicalize_txn_key(data: TransactionCreate) -> str:
    if data.idempotency_key:
        return data.idempotency_key.strip()

    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    payload["txn_timestamp"] = (
        payload["txn_timestamp"].isoformat()
        if getattr(payload.get("txn_timestamp"), "isoformat", None)
        else str(payload.get("txn_timestamp"))
    )
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _scoring_payload_from_txn(
    txn: Transaction, expected_monthly_inflow: float = 0.0
) -> dict:
    return {
        "amount": float(txn.amount),
        "txn_type": txn.txn_type,
        "direction": txn.direction,
        "counterparty_country": txn.counterparty_country,
        "txn_timestamp": txn.txn_timestamp,
        "expected_monthly_inflow": expected_monthly_inflow,
        "counterparty_name": txn.counterparty_name,
    }


async def _ensure_alert_for_transaction(
    db: AsyncSession,
    txn: Transaction,
    ensemble_score: float,
    rule_score: float,
    ml_score: float,
    flag_reasons: list[str],
    scorer_alert: bool,
):
    result = await db.execute(select(Alert).where(Alert.transaction_id == txn.id))
    existing_alert = result.scalar_one_or_none()
    if existing_alert:
        return existing_alert

    def generate_alert_id() -> str:
        date_str = datetime.utcnow().strftime("%Y%m%d")
        uid = str(uuid.uuid4().int)[:5]
        return f"ALT-{date_str}-{uid.zfill(5)}"

    severity = "LOW"
    if ensemble_score >= 80:
        severity = "CRITICAL"
    elif ensemble_score >= get_ml_alert_threshold():
        severity = "HIGH"
    elif ensemble_score >= 40:
        severity = "MEDIUM"

    if scorer_alert and flag_reasons:
        gen_by = "both"
    elif scorer_alert:
        gen_by = "scorer"
    else:
        gen_by = "rules"

    alert = Alert(
        id=generate_alert_id(),
        entity_id=txn.entity_id,
        transaction_id=txn.id,
        alert_type="aml",
        typology=(flag_reasons[0] if flag_reasons else "suspicious"),
        severity=severity,
        risk_score=float(ensemble_score),
        priority=(1 if severity in ("CRITICAL", "HIGH") else 3),
        status="OPEN",
        title=f"Automated alert for {txn.id}",
        description=f"Flags: {flag_reasons}; ml_score={ml_score:.3f}; ensemble={ensemble_score:.2f}",
        evidence=[],
        recommended_action=None,
        generated_by=gen_by,
        sar_required=(rule_score >= 80),
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


async def create_transaction(
    db: AsyncSession, data: TransactionCreate, entity=None
) -> Transaction:
    idem_key = _canonicalize_txn_key(data)

    async with db.begin():
        existing_result = await db.execute(
            select(Transaction).where(Transaction.idempotency_key == idem_key)
        )
        existing_txn = existing_result.scalar_one_or_none()
        if existing_txn:
            ent = entity or await _entity_service.get_entity(db, existing_txn.entity_id)
            payload = _scoring_payload_from_txn(
                existing_txn, float(getattr(ent, "expected_monthly_inflow", 0) or 0)
            )
            scored = score_txn(payload)
            flag_reasons, rule_score = run_rules(data)
            existing_txn.risk_score = float(rule_score)
            existing_txn.ml_score = float(scored.get("ml_score", 0.0))
            existing_txn.is_flagged = bool(scored.get("alert", False))
            await _entity_service.update_risk_scores(
                db,
                existing_txn.entity_id,
                float(
                    scored.get(
                        "ensemble_score",
                        get_ensemble_score(rule_score, existing_txn.ml_score),
                    )
                ),
                float(existing_txn.ml_score * 0.2),
                float(existing_txn.ml_score * 0.7),
                float(existing_txn.ml_score * 0.1),
            )
            final_alert = bool(scored.get("alert", False)) or should_generate_alert(
                float(
                    scored.get(
                        "ensemble_score",
                        get_ensemble_score(rule_score, existing_txn.ml_score),
                    )
                ),
                bool(flag_reasons),
            )
            if final_alert:
                await _ensure_alert_for_transaction(
                    db,
                    existing_txn,
                    float(
                        scored.get(
                            "ensemble_score",
                            get_ensemble_score(rule_score, existing_txn.ml_score),
                        )
                    ),
                    float(rule_score),
                    float(existing_txn.ml_score),
                    flag_reasons,
                    bool(scored.get("alert", False)),
                )
            return existing_txn

        flag_reasons, rule_score = run_rules(data)
        is_flagged = len(flag_reasons) > 0
        rules_flagged = is_flagged

        txn = Transaction(
            id=generate_txn_id(),
            idempotency_key=idem_key,
            entity_id=data.entity_id,
            account_id=data.account_id,
            amount=data.amount,
            currency=data.currency,
            txn_type=data.txn_type,
            direction=data.direction,
            channel=data.channel,
            counterparty_name=data.counterparty_name,
            counterparty_account=data.counterparty_account,
            counterparty_bank=data.counterparty_bank,
            counterparty_country=data.counterparty_country,
            merchant_name=data.merchant_name,
            merchant_category=data.merchant_category,
            location_city=data.location_city,
            location_country=data.location_country,
            risk_score=rule_score,
            is_flagged=is_flagged,
            flag_reasons=flag_reasons,
            rule_hits=flag_reasons,
            txn_timestamp=data.txn_timestamp,
            notes=data.notes,
        )
        db.add(txn)
        await db.flush()
        await db.refresh(txn)

        try:
            ent = entity or await _entity_service.get_entity(db, data.entity_id)
            scored = score_txn(
                _scoring_payload_from_txn(
                    txn, float(getattr(ent, "expected_monthly_inflow", 0) or 0)
                )
            )
            ml_score = float(scored.get("ml_score", 0.0))
            ensemble_score = float(
                scored.get("ensemble_score", get_ensemble_score(rule_score, ml_score))
            )
        except Exception:
            await record_scoring_failure(
                db,
                transaction_id=txn.id,
                entity_id=txn.entity_id,
                failure_reason="scoring_exception",
                details={"entity_id": txn.entity_id, "txn_type": txn.txn_type},
            )
            try:
                SCORING_FAILURES.inc()
            except Exception:
                pass
            scored = {}
            ml_score = 0.0
            ensemble_score = get_ensemble_score(rule_score, ml_score)

        txn.ml_score = float(ml_score)

        scorer_alert = False
        try:
            scorer_alert = bool(scored.get("alert", False))
        except Exception:
            scorer_alert = False

        txn.is_flagged = bool(scorer_alert)

        try:
            await _entity_service.update_risk_scores(
                db,
                txn.entity_id,
                float(ensemble_score),
                float(ensemble_score * 0.2),
                float(ensemble_score * 0.7),
                float(ensemble_score * 0.1),
            )
        except Exception:
            pass

        final_alert = bool(scorer_alert) or should_generate_alert(
            ensemble_score, rules_flagged
        )
        if final_alert:
            await _ensure_alert_for_transaction(
                db,
                txn,
                float(ensemble_score),
                float(rule_score),
                float(ml_score),
                flag_reasons,
                bool(scorer_alert),
            )

        return txn


async def get_transactions(
    db: AsyncSession,
    entity_id: str = None,
    flagged_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> list[Transaction]:
    query = select(Transaction)
    if entity_id:
        query = query.where(Transaction.entity_id == entity_id)
    if flagged_only:
        query = query.where(Transaction.is_flagged is True)
    query = query.order_by(Transaction.txn_timestamp.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
