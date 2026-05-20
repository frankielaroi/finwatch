import asyncio
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

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


async def run_retrain(
    database_url: Optional[str] = None, promote_if_better: bool = True
) -> dict:
    """Train a new model and register it in the model registry.
    Returns dict with version and metrics.
    """
    # Create synthetic features if not present
    features_csv = Path("/tmp/finwatch_features.csv")
    if not features_csv.exists():
        # generate CSV with label
        generate(str(features_csv), n=2000)

    # split into train / holdout
    import pandas as pd

    df = pd.read_csv(features_csv)
    df_shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)
    split = int(len(df_shuffled) * 0.8)
    train_df = df_shuffled.iloc[:split]
    holdout_df = df_shuffled.iloc[split:]
    train_csv = features_csv.with_name(
        f"finwatch_train_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
    )
    holdout_csv = features_csv.with_name(
        f"finwatch_holdout_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
    )
    train_df.to_csv(train_csv, index=False)
    holdout_df.to_csv(holdout_csv, index=False)

    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    artifact_path = str(MODELS_DIR.joinpath(f"fraud_model_{version}.pkl"))

    # train in thread to avoid blocking
    await asyncio.to_thread(train, str(train_csv), "label", artifact_path)

    # evaluate on holdout
    eval_out = Path("/tmp") / f"eval_{version}.json"
    await asyncio.to_thread(evaluate, artifact_path, str(holdout_csv), str(eval_out))
    try:
        import json

        with open(eval_out, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    except Exception:
        metrics = {}

    # calibration and extra validation
    try:
        val = validate_model_on_csv(artifact_path, holdout_csv)
        calibration = val.get("calibration")
        metrics.update(val.get("metrics", {}))
    except Exception:
        calibration = None

    # compute a small artifact hash for lineage
    try:
        with open(artifact_path, "rb") as f:
            training_hash = hashlib.sha256(f.read(1024)).hexdigest()
    except Exception:
        training_hash = None

    db_url = (
        database_url
        or os.environ.get("ASYNC_DATABASE_URL")
        or os.environ.get("ASYNC_DATABASE_URI")
    )
    if not db_url:
        return {"version": version, "metrics": metrics, "registered": False}

    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db:
        await register_model_version(
            db,
            model_name=MODEL_NAME,
            version=version,
            artifact_path=str(artifact_path),
            metrics=metrics,
            calibration=calibration,
            training_data_hash=training_hash,
            trained_at=datetime.utcnow(),
        )
        await db.commit()
        # Do not auto-promote in retrain job. Promotion is manual via CI/admin.
        promoted = False

    await engine.dispose()

    return {
        "version": version,
        "metrics": metrics,
        "registered": True,
        "promoted": promoted,
    }
