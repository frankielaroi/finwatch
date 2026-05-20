import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "FinWatch"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    ML_RULE_WEIGHT: float = 0.4
    ML_SCORE_WEIGHT: float = 0.6
    ML_ALERT_THRESHOLD: float = 60.0
    PROFILE_WORKER_INTERVAL_SECONDS: int = 300
    PROFILE_WORKER_BATCH_SIZE: int = 500
    PROFILE_WORKER_MAX_RUNTIME_SECONDS: int = 240
    PROFILE_WORKER_LOCK_TTL: int = 600
    PROFILE_DLQ_INTERVAL_SECONDS: int = 600
    PROFILE_DLQ_BATCH_SIZE: int = 200
    PROFILE_DLQ_MAX_ATTEMPTS: int = 5
    DLQ_ALERT_THRESHOLD: int = 50
    WORKER_FAILURE_ALERT_THRESHOLD: int = 3
    SCORING_FAILURE_ALERT_THRESHOLD: int = 5
    OPS_ALERT_WINDOW_MINUTES: int = 60
    AUTH_API_KEY: str = ""

    DATABASE_URL: str
    ASYNC_DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_ml_calibration_path() -> Path:
    return Path("app/ml/calibration.json")


def get_ml_calibration() -> dict:
    path = get_ml_calibration_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def get_ml_rule_weight() -> float:
    calibration = get_ml_calibration()
    return float(calibration.get("rule_weight", settings.ML_RULE_WEIGHT))


def get_ml_score_weight() -> float:
    calibration = get_ml_calibration()
    return float(calibration.get("ml_weight", settings.ML_SCORE_WEIGHT))


def get_ml_alert_threshold() -> float:
    calibration = get_ml_calibration()
    return float(calibration.get("alert_threshold", settings.ML_ALERT_THRESHOLD))
