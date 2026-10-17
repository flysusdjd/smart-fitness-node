"""项目配置中心：集中读取路径、BLE UUID、模型文件、MySQL 与认证令牌相关参数。"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


# 项目根目录是所有数据、模型和静态资源路径的基准。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


# 把环境变量中的开关字符串转换成布尔值，便于配置 MySQL 等功能。
def _get_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


# 根据分散的 MySQL 配置拼出 SQLAlchemy 可用的连接串。
def _build_mysql_url() -> str:
    user = quote_plus(MYSQL_USER)
    password = quote_plus(MYSQL_PASSWORD)
    host = MYSQL_HOST
    port = MYSQL_PORT
    database = MYSQL_DATABASE
    auth_part = f"{user}:{password}" if MYSQL_PASSWORD else user
    return f"mysql+pymysql://{auth_part}@{host}:{port}/{database}?charset=utf8mb4"

# 采集、处理、模型三个目录和训练脚本保持同一套路径约定。
RAW_DATA_ROOT = PROJECT_ROOT / "ml_pipeline" / "data" / "raw"
PROCESSED_ROOT = PROJECT_ROOT / "ml_pipeline" / "data" / "processed"
MODELS_ROOT = PROJECT_ROOT / "ml_pipeline" / "data" / "models"

# BLE 名称和 UUID 必须与 ESP32 固件、Android 客户端保持一致。
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

# 数据库默认关闭，部署或演示需要持久化时通过 .env 打开。
MYSQL_ENABLED = _get_bool_env("MYSQL_ENABLED", False)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_fitness")
DATABASE_URL = os.getenv("DATABASE_URL") or _build_mysql_url()
DATABASE_ECHO = _get_bool_env("DATABASE_ECHO", False)
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "168"))
