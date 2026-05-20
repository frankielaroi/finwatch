"""Score a transaction: extract features, get ml_score, compute rule score, ensemble, and decision."""
from __future__ import annotations

from typing import Any, Dict

from app.core.config import (get_ml_alert_threshold, get_ml_rule_weight,
                             get_ml_score_weight)
from app.ml.features import extract_features
from app.ml.generate_synthetic import rule_score_for_amount
from app.ml.predictor import predict_ml_score


def score_transaction(txn: Dict[str, Any]) -> Dict[str, Any]:
    """Return a dict with features, ml_score (0-1), rule_score(0-100), ensemble_score, and alert boolean."""
    # rule_score_for_amount expects (amount, txn_type, counterparty_country, counterparty_name)
    amount = float(txn.get("amount") or 0.0)
    txn_type = txn.get("txn_type")
    country = txn.get("counterparty_country")
    counterparty_name = txn.get("counterparty_name")

    rule_score = float(
        rule_score_for_amount(amount, txn_type, country, counterparty_name)
    )

    features = extract_features(txn)
    ml_score = float(predict_ml_score(features))

    ensemble = (rule_score * get_ml_rule_weight()) + (
        ml_score * 100.0 * get_ml_score_weight()
    )

    alert = ensemble >= get_ml_alert_threshold() or rule_score > 0

    return {
        "features": features,
        "ml_score": ml_score,
        "rule_score": rule_score,
        "ensemble_score": float(ensemble),
        "alert": bool(alert),
    }


if __name__ == "__main__":
    # small demo
    sample = {
        "amount": 9500,
        "txn_type": "cash_deposit",
        "direction": "outbound",
        "counterparty_country": "IR",
        "txn_timestamp": None,
        "expected_monthly_inflow": 1000,
        "counterparty_name": None,
    }
    print(score_transaction(sample))
