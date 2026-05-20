"""Train a classifier and save to `app/ml/models/fraud_model.pkl`.

Uses XGBoost when available; otherwise falls back to sklearn's GradientBoostingClassifier.
"""
from __future__ import annotations

import argparse
import os

import joblib
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from app.ml.features import build_feature_matrix

try:
    from xgboost import XGBClassifier

    XGB_AVAILABLE = True
except Exception:
    XGB_AVAILABLE = False
    from sklearn.ensemble import GradientBoostingClassifier


def train(
    input_csv: str,
    label_col: str = "label",
    out_path: str = "app/ml/models/fraud_model.pkl",
    test_size: float = 0.2,
    random_state: int = 42,
):
    df = pd.read_csv(input_csv)
    if label_col not in df.columns:
        raise ValueError(f"Label column {label_col} not in {input_csv}")
    rows = df.to_dict(orient="records")
    X = build_feature_matrix(rows)
    y = df[label_col].astype(int).values

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y if len(set(y)) > 1 else None,
    )

    if XGB_AVAILABLE:
        model = XGBClassifier(
            n_estimators=200,
            learning_rate=0.05,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        try:
            model.fit(
                X_train,
                y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=10,
                verbose=False,
            )
        except TypeError:
            model.fit(X_train, y_train)
    else:
        model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.05)
        model.fit(X_train, y_train)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    joblib.dump(model, out_path)
    print(f"Saved model to {out_path}")

    try:
        preds = model.predict(X_val)
        probs = model.predict_proba(X_val)[:, 1]
        print(classification_report(y_val, preds))
        try:
            print("ROC AUC:", roc_auc_score(y_val, probs))
        except Exception:
            pass
    except Exception:
        print("Could not evaluate model on validation set")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--label", default="label")
    p.add_argument("--out", default="app/ml/models/fraud_model.pkl")
    args = p.parse_args(argv)
    train(args.input, args.label, args.out)


if __name__ == "__main__":
    main()
