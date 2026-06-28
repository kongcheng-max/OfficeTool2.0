"""Celery 配置"""

import asyncio
import sys
import os
from typing import Any, Callable, Coroutine

from loguru import logger

# 确保 Celery fork 子进程能正确导入项目模块
_proj_root = os.environ.get("PROJ_ROOT", "/app")
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from celery import Celery

from core.config import settings

celery_app = Celery(
    "officetool",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.parse", "tasks.embed", "tasks.kg_build"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.PARSE_TIMEOUT_SECONDS,
    task_time_limit=settings.PARSE_TIMEOUT_SECONDS + 60,
)


# ========================================================================
# BUG-039 修复: Celery threads pool 安全执行 async 函数
# ========================================================================

def run_async_in_worker(coro_factory: Callable[[], Coroutine]) -> Any:
    """在 Celery Worker 线程中安全运行异步协程

    修复 asyncio event loop 冲突:
    - 线程池模式下, asyncio.run() 自动创建/清理 event loop
    - 异常时确保 loop 资源被释放
    - 兼容 Python 3.11+ 的 event loop 管理

    Usage:
        def my_task(self, doc_id):
            return run_async_in_worker(lambda: _async_work(doc_id))
    """
    try:
        return asyncio.run(coro_factory())
    except RuntimeError as e:
        # 如果当前线程已有运行中的 event loop (边缘情况)
        if "event loop" in str(e).lower():
            logger.debug(f"线程已有 event loop, 创建新 loop: {e}")
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro_factory())
            finally:
                loop.close()
        raise
