"""Q&A 答案缓存 — Redis 缓存 LLM 对相同问题的回答

Phase 3 W10.1: 相同问题 1h 内直接返回缓存答案，节省 LLM 调用成本 + 降低延迟。
"""

import hashlib
import json
from typing import Optional

from loguru import logger


class QACache:
    """问答结果缓存

    Key: qa_cache:{kb_id}:{question_md5}
    TTL: 1 小时（相同问题在短时间内重复提问很常见）
    """

    TTL = 3600  # 1 小时

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        """延迟初始化 Redis"""
        import redis.asyncio as aioredis
        from core.config import settings

        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,
                    socket_connect_timeout=3,
                )
                await self._redis.ping()
                logger.info("QA 缓存: Redis 已连接")
            except Exception as e:
                logger.info(f"QA 缓存: Redis 不可用 ({e})，跳过缓存")
                self._redis = False
        if self._redis is False:
            return None
        return self._redis

    @staticmethod
    def _cache_key(kb_id: str, question: str) -> str:
        """生成缓存 key — 归一化问题文本后取 MD5"""
        normalized = question.strip().lower()
        q_hash = hashlib.md5(
            normalized.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:16]
        return f"qa_cache:{kb_id}:{q_hash}"

    async def get(self, kb_id: str, question: str) -> Optional[dict]:
        """查询缓存 — 命中返回完整回答 dict，未命中返回 None"""
        r = await self._get_redis()
        if not r:
            return None
        try:
            data = await r.get(self._cache_key(kb_id, question))
            if data:
                cached = json.loads(data.decode("utf-8"))
                logger.info(
                    f"QA 缓存命中: kb={kb_id}, q='{question[:50]}...'"
                )
                return cached
        except Exception as e:
            logger.warning(f"QA 缓存读取失败: {e}")
        return None

    async def set(self, kb_id: str, question: str, answer: dict):
        """写入缓存"""
        r = await self._get_redis()
        if not r:
            return
        try:
            data = json.dumps(answer, ensure_ascii=False).encode("utf-8")
            await r.setex(self._cache_key(kb_id, question), self.TTL, data)
            logger.info(
                f"QA 缓存写入: kb={kb_id}, q='{question[:50]}...', ttl={self.TTL}s"
            )
        except Exception as e:
            logger.warning(f"QA 缓存写入失败: {e}")

    async def invalidate_kb(self, kb_id: str):
        """知识库内容变更时清除缓存（文档上传/删除后调用）"""
        r = await self._get_redis()
        if not r:
            return
        try:
            pattern = f"qa_cache:{kb_id}:*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            if deleted:
                logger.info(f"QA 缓存清理: kb={kb_id}, keys={deleted}")
        except Exception as e:
            logger.warning(f"QA 缓存清理失败: {e}")


# 全局单例
qa_cache = QACache()
