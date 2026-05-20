"""Train an XGBoost model from historical CSV data.

Usage:
    python -m app.ml.train --input data/historical.csv --label label --out-joblib app/ml/model.joblib

CSV must contain columns: amount, txn_type, direction, counterparty_country, txn_timestamp, expected_monthly_inflow, and a label column (0/1).
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

try:
    import xgboost as xgb
    from xgboost import XGBClassifier
except Exception:
    xgb = None
    XGBClassifier = None

import joblib

from app.ml.features import build_feature_matrix


def load_data(path: str, label_col: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found in CSV")
    return df


def prepare_xy(df: pd.DataFrame, label_col: str):
    rows = df.to_dict(orient="records")
    X = build_feature_matrix(rows)
    y = df[label_col].astype(int).values
    return X, y


def train(args: argparse.Namespace):
    if XGBClassifier is None:
        print("xgboost is not installed. Install xgboost to train a model.")
        sys.exit(1)

    df = load_data(args.input, args.label)
    X, y = prepare_xy(df, args.label)

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y if args.stratify else None,
    )

    model = XGBClassifier(
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        use_label_encoder=False,
        eval_metric="logloss",
    )

    try:
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=10,
            verbose=True,
        )
    except TypeError:
        # Older xgboost versions' sklearn wrapper may not accept early_stopping_rounds
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=True)

    # Save model
    out_joblib = args.out_joblib or "app/ml/model.joblib"
    os.makedirs(os.path.dirname(out_joblib), exist_ok=True)
    joblib.dump(model, out_joblib)
    print(f"Saved model to {out_joblib}")

    # also save raw booster if available
    try:
        booster = model.get_booster()
        out_bst = args.out_bst or "app/ml/xgb_model.bst"
        booster.save_model(out_bst)
        print(f"Saved booster to {out_bst}")
    except Exception:
        pass

    preds = model.predict(X_val)
    probs = model.predict_proba(X_val)[:, 1]
    print(classification_report(y_val, preds))
    try:
        print("ROC AUC:", roc_auc_score(y_val, probs))
    except Exception:
        pass


def main(argv: Optional[list[str]] = None):
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to historical CSV")
    p.add_argument("--label", default="label", help="Label column name (0/1)")
    p.add_argument("--out-joblib", default="app/ml/model.joblib")
    p.add_argument("--out-bst", default="app/ml/xgb_model.bst")
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--learning-rate", type=float, default=0.05)
    p.add_argument("--stratify", action="store_true")
    args = p.parse_args(argv)
    train(args)


if __name__ == "__main__":
    main()
