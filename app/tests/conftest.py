"""Pytest 配置 — 设置测试环境变量

必须在任何测试模块导入前设置 USE_SQLITE，
确保 core.database 使用 SQLite 而非 PostgreSQL。
"""
import os

os.environ["USE_SQLITE"] = "true"
# Use in-memory SQLite to avoid file-locking issues with pytest-asyncio on Windows
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
