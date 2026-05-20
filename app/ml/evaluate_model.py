"""Evaluate trained model on a feature CSV and save metrics report.

Usage:
    python -m app.ml.evaluate_model --model app/ml/model.joblib --features app/ml/features_matrix.csv --out app/ml/eval_report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, f1_score,
                             precision_score, recall_score, roc_auc_score)


def load_model(path: Path):
    # Try joblib first
    try:
        model = joblib.load(path)
        return model
    except Exception:
        pass

    # Try xgboost booster
    try:
        import xgboost as xgb

        bst = xgb.Booster()
        bst.load_model(str(path))
        return bst
    except Exception:
        raise RuntimeError(f"Could not load model from {path}")


def predict_proba(model, X: pd.DataFrame) -> np.ndarray:
    # sklearn-like model
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)
        if probs.ndim == 2:
            return probs[:, 1]
        return probs

    # sklearn-like predict returning array of floats
    if hasattr(model, "predict") and not hasattr(model, "predict_proba"):
        preds = model.predict(X)
        return np.asarray(preds)

    # xgboost.Booster
    try:
        import xgboost as xgb

        if isinstance(model, xgb.core.Booster):
            dmat = xgb.DMatrix(X.values)
            out = model.predict(dmat)
            return np.asarray(out)
    except Exception:
        pass

    raise RuntimeError("Model does not support prediction")


def evaluate(model_path: str, features_csv: str, out_path: str):
    mpath = Path(model_path)
    fpath = Path(features_csv)
    outp = Path(out_path)

    df = pd.read_csv(fpath)
    if "label" not in df.columns:
        print("Features CSV must contain a 'label' column", file=sys.stderr)
        sys.exit(2)

    y = df["label"].astype(int).values
    X = df.drop(columns=["label"])

    model = load_model(mpath)
    probs = predict_proba(model, X)

    # If probs are not in [0,1], normalize if possible
    probs = np.asarray(probs, dtype=float)
    if probs.min() < 0 or probs.max() > 1:
        # Min-max scale
        probs = (probs - probs.min()) / (probs.max() - probs.min() + 1e-12)

    preds = (probs >= 0.5).astype(int)

    report = {}
    report["n_samples"] = int(len(y))
    report["accuracy"] = float(accuracy_score(y, preds))
    report["precision"] = float(precision_score(y, preds, zero_division=0))
    report["recall"] = float(recall_score(y, preds, zero_division=0))
    report["f1"] = float(f1_score(y, preds, zero_division=0))
    try:
        report["roc_auc"] = float(roc_auc_score(y, probs))
    except Exception:
        report["roc_auc"] = None
    try:
        report["avg_precision"] = float(average_precision_score(y, probs))
    except Exception:
        report["avg_precision"] = None

    # Save per-class sample counts
    unique, counts = np.unique(y, return_counts=True)
    report["label_counts"] = {str(int(k)): int(v) for k, v in zip(unique, counts)}

    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Print a short summary
    print(json.dumps(report, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--features", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    evaluate(args.model, args.features, args.out)


if __name__ == "__main__":
    main()
