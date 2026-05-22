from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


def _get_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _build_mysql_url() -> str:
    user = quote_plus(MYSQL_USER)
    password = quote_plus(MYSQL_PASSWORD)
    host = MYSQL_HOST
    port = MYSQL_PORT
    database = MYSQL_DATABASE
    auth_part = f"{user}:{password}" if MYSQL_PASSWORD else user
    return f"mysql+pymysql://{auth_part}@{host}:{port}/{database}?charset=utf8mb4"

RAW_DATA_ROOT = PROJECT_ROOT / "ml_pipeline" / "data" / "raw"
PROCESSED_ROOT = PROJECT_ROOT / "ml_pipeline" / "data" / "processed"
MODELS_ROOT = PROJECT_ROOT / "ml_pipeline" / "data" / "models"

DEVICE_NAME = "ESP32S3_Fitness_BLE"
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

DEFAULT_SCAN_TIMEOUT_S = 5.0
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_INFERENCE_WINDOW_SIZE = 20

MODEL_PATH = MODELS_ROOT / "random_forest_model.joblib"
LABEL_MAP_PATH = PROCESSED_ROOT / "labels" / "label_map.json"
DATASET_META_PATH = PROCESSED_ROOT / "labels" / "dataset_meta.json"
ADVANCED_EVAL_PROFILE_PATH = MODELS_ROOT / "advanced_evaluation_profile.json"

RECOMMENDED_LABELS = [
    "idle",
    "squat_standard",
    "squat_wrong",
    "bench_standard",
    "bench_wrong",
]

MYSQL_ENABLED = _get_bool_env("MYSQL_ENABLED", False)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_fitness")
DATABASE_URL = os.getenv("DATABASE_URL") or _build_mysql_url()
DATABASE_ECHO = _get_bool_env("DATABASE_ECHO", False)
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "168"))
