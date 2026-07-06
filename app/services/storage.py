"""文件存储服务 — MinIO（可选）+ 本地文件兜底"""

import hashlib
import os
from io import BytesIO
from pathlib import Path

from loguru import logger

from core.config import settings


class StorageService:
    """文件存储封装 — 优先 MinIO，不可用时降级到本地文件系统"""

    def __init__(self):
        self._client = None
        self._minio_available: bool | None = None  # None = 未检测

    @property
    def minio_available(self) -> bool:
        """检测 MinIO 是否可用（仅检测一次）"""
        if self._minio_available is None:
            # 凭证为空 → 跳过 MinIO
            if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
                logger.info("MinIO 未配置（缺少 ACCESS_KEY/SECRET_KEY），使用本地文件存储")
                self._minio_available = False
                return False
            try:
                from minio import Minio
                self._client = Minio(
                    endpoint=settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_SECURE,
                )
                self._client.bucket_exists(settings.MINIO_BUCKET)
                self._minio_available = True
                logger.info(f"MinIO 已连接: {settings.MINIO_ENDPOINT}")
            except Exception as e:
                logger.warning(f"MinIO 不可用 ({e})，使用本地文件存储")
                self._minio_available = False
        return self._minio_available

    def _local_path(self, object_name: str) -> str:
        """将对象名转为本地路径"""
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        safe_name = object_name.replace("/", "_").replace("\\", "_")
        return os.path.join(settings.UPLOAD_DIR, safe_name)

    async def ensure_bucket(self):
        """确保存储桶存在（MinIO 模式）"""
        if self.minio_available:
            try:
                from minio.error import S3Error
                if not self._client.bucket_exists(settings.MINIO_BUCKET):
                    self._client.make_bucket(settings.MINIO_BUCKET)
                    logger.info(f"创建 MinIO 存储桶: {settings.MINIO_BUCKET}")
            except S3Error as e:
                logger.error(f"MinIO 存储桶检查失败: {e}")

    async def upload(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传文件，返回存储路径"""
        if self.minio_available:
            await self.ensure_bucket()
            self._client.put_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
                data=BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )
            return object_name
        else:
            local_path = self._local_path(object_name)
            with open(local_path, "wb") as f:
                f.write(file_data)
            logger.debug(f"本地存储: {local_path}")
            return local_path

    async def download(self, object_name: str) -> bytes:
        """下载文件"""
        # 本地路径直接读取
        if object_name.startswith(settings.UPLOAD_DIR) or os.path.isabs(object_name):
            with open(object_name, "rb") as f:
                return f.read()
        # MinIO 路径
        if self.minio_available:
            response = self._client.get_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
            )
            return response.read()
        # 兜底：尝试本地
        local_path = self._local_path(object_name)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"文件不存在: {object_name}")

    async def delete(self, object_name: str):
        """删除文件"""
        if object_name.startswith(settings.UPLOAD_DIR) or os.path.isabs(object_name):
            try:
                os.remove(object_name)
            except OSError:
                pass
            return
        if self.minio_available:
            self._client.remove_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
            )
        else:
            local_path = self._local_path(object_name)
            try:
                os.remove(local_path)
            except OSError:
                pass

    async def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """生成预签名下载 URL（MinIO 模式），本地模式返回空"""
        if self.minio_available and not object_name.startswith(settings.UPLOAD_DIR):
            return self._client.presigned_get_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_name,
                expires=expires,
            )
        return ""

    @staticmethod
    def compute_md5(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()


# 全局单例
storage_service = StorageService()
