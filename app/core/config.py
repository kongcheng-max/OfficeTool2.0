"""全局配置模块 — YAML + 环境变量驱动"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，支持 YAML 文件 + 环境变量覆盖"""

    # === 应用基础 ===
    APP_NAME: str = "OfficeTool"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    SECRET_KEY: str = ""  # 生产环境必须通过环境变量设置

    # === CORS ===
    # 允许的跨域来源列表；开发环境默认允许 Vite 前端
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # === 数据库 ===
    DATABASE_URL: str = "postgresql+asyncpg://officetool:officetool@localhost:5432/officetool"
    USE_SQLITE: bool = False  # 设为 True 使用 SQLite（无需外部 DB）
    DB_POOL_SIZE: int = 20  # 连接池大小（50 QPS 需求）
    DB_POOL_OVERFLOW: int = 10  # 连接池溢出上限
    DB_POOL_TIMEOUT: int = 30  # 获取连接超时秒数

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379/0"

    # === MinIO ===
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""  # 生产环境必须通过环境变量设置
    MINIO_SECRET_KEY: str = ""  # 生产环境必须通过环境变量设置
    MINIO_BUCKET: str = "officetool-documents"
    MINIO_SECURE: bool = False

    # === Milvus ===
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "officetool_chunks"

    # === Elasticsearch ===
    ELASTICSEARCH_URL: str = "http://localhost:9200"

    # === Neo4j ===
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

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
    KG_ENABLED: bool = True  # 设为 false 可跳过 KG 构建，加速测试

    # === 检索 ===
    RETRIEVER_TOP_K: int = 10

    # === 文件存储路径 ===
    UPLOAD_DIR: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @model_validator(mode="after")
    def validate_security_settings(self):
        """Raise a clear error if SECRET_KEY is empty in non-debug / production mode."""
        if not self.SECRET_KEY and not self.DEBUG:
            raise ValueError(
                "SECRET_KEY must be set via environment variable when DEBUG=False. "
                "Generate a random key: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

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
