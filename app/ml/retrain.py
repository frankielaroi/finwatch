from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.ml.evaluate_model import evaluate
from app.ml.generate_synthetic import generate
from app.ml.trainer import train
from app.ml.validation import validate_model_on_csv
from app.services.model_registry_service import register_model_version

MODEL_NAME = "fraud_model"
MODELS_DIR = Path("app/ml/models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def cli_main(database_url: str | None = None):
    # generate synthetic data if missing
    features_csv = Path("/tmp/finwatch_features.csv")
    if not features_csv.exists():
        generate(str(features_csv), n=2000)

    df = pd.read_csv(features_csv)
    df_shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)
    split = int(len(df_shuffled) * 0.8)
    train_df = df_shuffled.iloc[:split]
    holdout_df = df_shuffled.iloc[split:]
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    train_csv = features_csv.with_name(f"finwatch_train_{version}.csv")
    holdout_csv = features_csv.with_name(f"finwatch_holdout_{version}.csv")
    train_df.to_csv(train_csv, index=False)
    holdout_df.to_csv(holdout_csv, index=False)

    artifact_path = str(MODELS_DIR.joinpath(f"fraud_model_{version}.pkl"))
    # train
    train(str(train_csv), "label", artifact_path)

    # evaluate on holdout
    eval_out = Path("/tmp") / f"eval_{version}.json"
    evaluate(artifact_path, str(holdout_csv), str(eval_out))
    try:
        with open(eval_out, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    except Exception:
        metrics = {}

    # calibration
    try:
        val = validate_model_on_csv(artifact_path, holdout_csv)
        calibration = val.get("calibration")
        metrics.update(val.get("metrics", {}))
    except Exception:
        calibration = None

    # register model version in DB
    if not database_url:
        database_url = os.environ.get("ASYNC_DATABASE_URL")
    if not database_url:
        print("No ASYNC_DATABASE_URL provided; model saved locally but not registered")
        return

    engine = create_async_engine(database_url, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    training_hash = None
    try:
        with open(artifact_path, "rb") as f:
            training_hash = hashlib.sha256(f.read(1024)).hexdigest()
    except Exception:
        pass

    async def _register():
        async with AsyncSessionLocal() as db:
            mv = await register_model_version(
                db,
                model_name=MODEL_NAME,
                version=version,
                artifact_path=artifact_path,
                metrics=metrics,
                calibration=calibration,
                training_data_hash=training_hash,
                trained_at=datetime.utcnow(),
            )
            await db.commit()
            print("Registered model version", mv.version)
            print("Model registered as candidate. Promotion is manual via CI/admin.")

    asyncio.run(_register())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", help="Async DB URL (overrides ASYNC_DATABASE_URL env var)")
    args = p.parse_args()
    cli_main(args.db)


if __name__ == "__main__":
    main()
