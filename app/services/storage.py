"""MinIO 文件存储服务"""

import hashlib
from io import BytesIO
from pathlib import Path

from loguru import logger
from minio import Minio
from minio.error import S3Error

from core.config import settings


class StorageService:
    """MinIO 对象存储封装"""

    def __init__(self):
        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        return self._client

    async def ensure_bucket(self):
        """确保存储桶存在"""
        try:
            if not self.client.bucket_exists(settings.MINIO_BUCKET):
                self.client.make_bucket(settings.MINIO_BUCKET)
                logger.info(f"创建 MinIO 存储桶: {settings.MINIO_BUCKET}")
        except S3Error as e:
            logger.error(f"MinIO 存储桶检查失败: {e}")

    async def upload(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传文件到 MinIO，返回对象路径"""
        await self.ensure_bucket()
        self.client.put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            data=BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
        )
        return object_name

    async def download(self, object_name: str) -> bytes:
        """从 MinIO 下载文件"""
        response = self.client.get_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
        )
        return response.read()

    async def delete(self, object_name: str):
        """从 MinIO 删除文件"""
        self.client.remove_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
        )

    async def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """生成预签名下载 URL"""
        return self.client.presigned_get_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            expires=expires,
        )

    @staticmethod
    def compute_md5(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()


# 全局单例
storage_service = StorageService()
