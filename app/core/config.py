"""全局配置模块 — YAML + 环境变量驱动"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置，支持 YAML 文件 + 环境变量覆盖"""

    # === 应用基础 ===
    APP_NAME: str = "OfficeTool"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret"

    # === 数据库 ===
    DATABASE_URL: str = "postgresql+asyncpg://officetool:officetool@localhost:5432/officetool"
    USE_SQLITE: bool = False  # 设为 True 使用 SQLite（无需外部 DB）

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379/0"

    # === MinIO ===
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "officetool-documents"
    MINIO_SECURE: bool = False

    # === Milvus ===
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "officetool_chunks"

    # === JWT ===
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时

    # === LLM ===
    LLM_PROVIDER: str = "tongyi"  # "tongyi" | "deepseek"
    LLM_TONGYI_API_KEY: Optional[str] = None
    LLM_TONGYI_MODEL: str = "qwen-max"
    LLM_DEEPSEEK_API_KEY: Optional[str] = None
    LLM_DEEPSEEK_MODEL: str = "deepseek-chat"

    # === Embedding ===
    EMBEDDING_MODEL: str = "text2vec-large-chinese"
    EMBEDDING_DEVICE: str = "cpu"

    # === Celery ===
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # === 解析 ===
    PARSE_TIMEOUT_SECONDS: int = 600
    MAX_FILE_SIZE_MB: int = 200

    # === 检索 ===
    RETRIEVER_TOP_K: int = 10

    # === 文件存储路径 ===
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def from_yaml(cls, yaml_path: str = "config.yaml") -> "Settings":
        """从 YAML 配置文件加载设置（环境变量优先覆盖）"""
        path = Path(yaml_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
            if yaml_config:
                return cls(**yaml_config)
        return cls()


# 全局单例
settings = Settings()
