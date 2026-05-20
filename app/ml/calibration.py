"""Calibrate the ensemble alert threshold from labeled historical data.

Usage:
    python -m app.ml.calibration --input data/synthetic.csv --label label --out app/ml/calibration.json

The script evaluates thresholds on a validation split and selects the one with the best F1.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from app.ml.features import build_feature_matrix
from app.ml.predictor import load_model, predict_ml_score


@dataclass
class CalibrationResult:
    threshold: float
    precision: float
    recall: float
    f1: float


def ensemble_score(
    rule_score: float, ml_score: float, rule_weight: float, ml_weight: float
) -> float:
    return (rule_score * rule_weight) + (ml_score * 100.0 * ml_weight)


def derive_rule_score(row: dict) -> float:
    score = 0.0
    amount = float(row.get("amount") or 0.0)
    txn_type = row.get("txn_type")
    counterparty_country = row.get("counterparty_country")
    counterparty_name = row.get("counterparty_name")
    if txn_type == "cash_deposit" and amount >= 10000:
        score += 30
    if 9000 <= amount < 10000 and txn_type == "cash_deposit":
        score += 40
    if counterparty_country in {
        "IR",
        "KP",
        "SY",
        "CU",
        "VE",
        "MM",
        "AF",
        "LY",
        "SO",
        "YE",
    }:
        score += 35
    if amount % 1000 == 0 and amount >= 5000:
        score += 10
    if txn_type == "wire_out" and amount >= 50000:
        score += 25
    if amount >= 5000 and not counterparty_name:
        score += 15
    return min(score, 100.0)


def calibrate(
    df: pd.DataFrame, label_col: str, rule_weight: float, ml_weight: float
) -> CalibrationResult:
    rows = df.to_dict(orient="records")
    X = build_feature_matrix(rows)
    y = df[label_col].astype(int).tolist()

    _, X_val, _, y_val, rows_train, rows_val = train_test_split(
        X, y, rows, test_size=0.25, random_state=42, stratify=y
    )

    # Load current model once so predict_ml_score uses it
    load_model()

    val_scores = []
    for row, features in zip(rows_val, X_val):
        rule_score = derive_rule_score(row)
        ml_score = predict_ml_score(features)
        val_scores.append(ensemble_score(rule_score, ml_score, rule_weight, ml_weight))

    best = CalibrationResult(threshold=60.0, precision=0.0, recall=0.0, f1=0.0)
    for threshold in [x / 10.0 for x in range(300, 901)]:
        preds = [1 if s >= threshold else 0 for s in val_scores]
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_val, preds, average="binary", zero_division=0
        )
        if f1 > best.f1:
            best = CalibrationResult(
                threshold=threshold, precision=precision, recall=recall, f1=f1
            )

    return best


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--label", default="label")
    parser.add_argument("--out", default="app/ml/calibration.json")
    parser.add_argument("--rule-weight", type=float, default=0.4)
    parser.add_argument("--ml-weight", type=float, default=0.6)
    args = parser.parse_args(argv)

    df = pd.read_csv(args.input)
    result = calibrate(df, args.label, args.rule_weight, args.ml_weight)

    payload = {
        "alert_threshold": result.threshold,
        "rule_weight": args.rule_weight,
        "ml_weight": args.ml_weight,
        "precision": result.precision,
        "recall": result.recall,
        "f1": result.f1,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
