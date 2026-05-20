from __future__ import annotations

import math
import os
from typing import Sequence

MODEL_PATHS = [
    "app/ml/models/fraud_model.pkl",
    "app/ml/models/fraud_model.joblib",
    "app/ml/xgb_model.bst",
    "app/ml/xgb_model.json",
    "app/ml/model.bst",
]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class FallbackModel:
    """Simple heuristic model used when no XGBoost model is available."""

    def predict_proba(self, X: Sequence[Sequence[float]]) -> Sequence[float]:
        out = []
        for row in X:
            # row order: amount_zscore, is_just_below_10k, is_high_risk_country,
            # is_round_number, is_large_wire, hour_of_day, txn_type_encoded, direction_encoded
            (
                amount_z,
                just_below,
                high_risk,
                round_num,
                large_wire,
                hour,
                ttype,
                direction,
            ) = row
            score = 0.0
            score += min(amount_z / 10.0, 2.0) * 1.2
            score += just_below * 1.5
            score += high_risk * 2.0
            score += round_num * 0.5
            score += large_wire * 1.8
            # odd hours (night) weight
            if hour < 6 or hour > 20:
                score += 0.8
            # txn type and direction adjustments
            score += (ttype % 3) * 0.2
            score += direction * 0.4
            out.append(_sigmoid(score))
        return out


def load_model():
    try:
        import xgboost as xgb
    except Exception:
        return FallbackModel()

    for p in MODEL_PATHS:
        if os.path.exists(p):
            try:
                # attempt to load Booster
                bst = xgb.Booster()
                bst.load_model(p)
                return bst
            except Exception:
                try:
                    # try sklearn wrapper
                    import joblib

                    return joblib.load(p)
                except Exception:
                    continue
    return FallbackModel()


_MODEL = load_model()


def predict_ml_score(feature_vector: Sequence[float]) -> float:
    """Return ml_score in [0.0, 1.0]."""
    if hasattr(_MODEL, "predict_proba"):
        proba = _MODEL.predict_proba([feature_vector])[0]
        # If predict_proba returns array-like with two cols, take positive class
        try:
            # handle numpy arrays and other sequences
            if hasattr(proba, "__len__") and len(proba) >= 2:
                return float(proba[1])
        except Exception:
            pass
        # fallback: try to cast to float (may fail)
        try:
            return float(proba)
        except Exception:
            # final fallback: use sigmoid on first element if possible
            try:
                return float(_sigmoid(float(proba)))
            except Exception:
                return 0.0

    # xgboost Booster
    try:
        import xgboost as xgb

        dmat = xgb.DMatrix([feature_vector])
        out = _MODEL.predict(dmat)
        # xgboost returns array
        val = float(out[0])
        # clamp
        return max(0.0, min(1.0, val))
    except Exception:
        # final fallback: heuristic
        return FallbackModel().predict_proba([feature_vector])[0]
