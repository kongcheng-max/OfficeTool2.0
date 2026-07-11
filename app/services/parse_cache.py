"""解析结果缓存层 — Redis 缓存 chunks，相同文件跳过重解析

Phase 3 W9.3: 相同 MD5 文件直接复用解析结果，避免重复解析。
"""

import json
from typing import List, Optional

from loguru import logger

from core.config import settings


class ParseCache:
    """解析结果缓存

    以文件 MD5 为 key 缓存解析后的 chunks JSON。
    仅缓存纯文本/结构化解析结果（~KB 级），不缓存 embedding 向量。
    """

    TTL = 3600 * 24 * 7  # 7 天

    def __init__(self):
        self._redis = None  # None=未初始化, False=不可用

    async def _get_redis(self):
        """延迟初始化 Redis"""
        import redis.asyncio as aioredis

        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,
                    socket_connect_timeout=3,
                )
                await self._redis.ping()
                logger.info("解析缓存: Redis 已连接")
            except Exception as e:
                logger.info(f"解析缓存: Redis 不可用 ({e})，跳过缓存")
                self._redis = False
        if self._redis is False:
            return None
        return self._redis

    def _cache_key(self, file_md5: str) -> str:
        return f"parse_cache:{file_md5}"

    async def get(self, file_md5: str) -> Optional[List[dict]]:
        """查询缓存 — 命中返回 chunks 列表，未命中返回 None"""
        if not file_md5:
            return None
        r = await self._get_redis()
        if not r:
            return None
        try:
            data = await r.get(self._cache_key(file_md5))
            if data:
                chunks = json.loads(data.decode("utf-8"))
                logger.info(
                    f"解析缓存命中: md5={file_md5[:12]}..., chunks={len(chunks)}"
                )
                return chunks
        except Exception as e:
            logger.warning(f"解析缓存读取失败: {e}")
        return None

    async def set(self, file_md5: str, chunks: List[dict]):
        """写入缓存"""
        if not file_md5 or not chunks:
            return
        r = await self._get_redis()
        if not r:
            return
        try:
            data = json.dumps(chunks, ensure_ascii=False).encode("utf-8")
            await r.setex(self._cache_key(file_md5), self.TTL, data)
            logger.info(
                f"解析缓存写入: md5={file_md5[:12]}..., chunks={len(chunks)}, ttl={self.TTL}s"
            )
        except Exception as e:
            logger.warning(f"解析缓存写入失败: {e}")

    async def invalidate(self, file_md5: str):
        """使缓存失效（文档替换/删除时调用）"""
        if not file_md5:
            return
        r = await self._get_redis()
        if not r:
            return
        try:
            await r.delete(self._cache_key(file_md5))
        except Exception:
            pass


# 全局单例
parse_cache = ParseCache()
