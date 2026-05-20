from datetime import datetime
from typing import Any, Dict, Sequence

HIGH_RISK_COUNTRIES = {"IR", "KP", "SY", "CU", "VE", "MM", "AF", "LY", "SO", "YE"}

TXN_TYPE_MAP = {
    "cash_deposit": 0,
    "wire_out": 1,
    "pos": 2,
    "transfer": 3,
    "check": 4,
}


def encode_txn_type(txn_type: str) -> int:
    if not txn_type:
        return 0
    return TXN_TYPE_MAP.get(txn_type.lower(), abs(hash(txn_type)) % 10)


def encode_direction(direction: str) -> int:
    if not direction:
        return 0
    return 0 if direction.lower() == "inbound" else 1


def extract_features(row: Dict[str, Any]) -> Sequence[float]:
    """Extract feature vector from a dict-like row.

    Expected keys: amount, txn_type, direction, counterparty_country, txn_timestamp, expected_monthly_inflow
    """
    amount = float(row.get("amount") or 0.0)
    expected = float(row.get("expected_monthly_inflow") or 0.0) or 1.0
    amount_zscore = amount / expected

    is_just_below_10k = (
        1 if 9000.0 <= amount < 10000.0 and row.get("txn_type") == "cash_deposit" else 0
    )
    is_high_risk = 1 if (row.get("counterparty_country") in HIGH_RISK_COUNTRIES) else 0
    is_round_number = 1 if amount % 1000 == 0 and amount >= 5000 else 0
    is_large_wire = 1 if row.get("txn_type") == "wire_out" and amount >= 50000 else 0

    ts = row.get("txn_timestamp")
    hour = 12
    if ts:
        if isinstance(ts, str):
            try:
                hour = datetime.fromisoformat(ts).hour
            except Exception:
                hour = 12
        elif isinstance(ts, datetime):
            hour = ts.hour

    txn_type_encoded = encode_txn_type(row.get("txn_type"))
    direction_encoded = encode_direction(row.get("direction"))

    return [
        amount_zscore,
        is_just_below_10k,
        is_high_risk,
        is_round_number,
        is_large_wire,
        float(hour),
        float(txn_type_encoded),
        float(direction_encoded),
    ]


def build_feature_matrix(rows: Sequence[Dict[str, Any]]):
    X = [extract_features(r) for r in rows]
    return X
