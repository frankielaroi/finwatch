from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss

from app.ml.evaluate_model import load_model, predict_proba


def expected_calibration_error(
    y_true: np.ndarray, probs: np.ndarray, n_bins: int = 10
) -> float:
    # ECE: sum over bins |acc - conf| * (|B_m|/N)
    prob = np.asarray(probs)
    truth = np.asarray(y_true)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    N = len(truth)
    for i in range(n_bins):
        mask = (prob >= bins[i]) & (prob < bins[i + 1])
        if not mask.any():
            continue
        conf = prob[mask].mean()
        acc = truth[mask].mean()
        ece += abs(acc - conf) * (mask.sum() / N)
    return float(ece)


def validate_model_on_csv(
    model_path: str | Path, features_csv: str | Path
) -> Dict[str, Any]:
    mpath = Path(model_path)
    fpath = Path(features_csv)
    df = pd.read_csv(fpath)
    if "label" not in df.columns:
        raise ValueError("Features CSV must contain 'label' column for validation")

    y = df["label"].astype(int).values
    X = df.drop(columns=["label"])

    model = load_model(mpath)
    probs = predict_proba(model, X)
    probs = np.asarray(probs, dtype=float)
    # clamp to [0,1]
    probs = np.clip(probs, 0.0, 1.0)

    brier = float(brier_score_loss(y, probs))
    ece = expected_calibration_error(y, probs, n_bins=10)

    # Simple calibration curve points
    frac_pos, mean_pred = calibration_curve(y, probs, n_bins=10)
    calib_points = {
        "fraction_positive": [float(x) for x in frac_pos],
        "mean_predicted": [float(x) for x in mean_pred],
    }

    metrics = {
        "brier_score": brier,
        "ece": ece,
    }

    calibration = {
        "points": calib_points,
        "brier_score": brier,
        "ece": ece,
    }

    return {"metrics": metrics, "calibration": calibration}
