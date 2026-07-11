"""文档 AES-256 加密层 — W11.6

可选开启：设置 DOC_ENCRYPTION_KEY 环境变量后，上传的文档原文将被加密存储。
密钥建议通过环境变量注入（不要硬编码到代码中）。
"""

import base64
import os
from typing import Optional

from loguru import logger

# 尝试导入 cryptography，不可用时优雅降级
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


class DocEncryption:
    """AES-256-CBC 文档加密器

    密钥管理：32 字节密钥 → base64 编码 → 环境变量 DOC_ENCRYPTION_KEY
    未设置密钥时，encrypt/decrypt 透明透传（无加密）。
    """

    def __init__(self):
        key_b64 = os.environ.get("DOC_ENCRYPTION_KEY", "")
        self._key: Optional[bytes] = None

        if key_b64 and _CRYPTO_AVAILABLE:
            try:
                key = base64.b64decode(key_b64)
                if len(key) == 32:
                    self._key = key
                    logger.info("AES-256 文档加密已启用")
                else:
                    logger.warning(
                        f"AES-256 密钥长度错误: {len(key)} (期望 32)"
                    )
            except Exception as e:
                logger.warning(f"AES-256 密钥解析失败: {e}")
        elif key_b64 and not _CRYPTO_AVAILABLE:
            logger.warning(
                "已设置 DOC_ENCRYPTION_KEY 但 cryptography 库未安装，加密不可用"
            )

    @property
    def enabled(self) -> bool:
        return self._key is not None

    def encrypt(self, plaintext: bytes) -> bytes:
        """加密字节数据 → 返回 IV + ciphertext"""
        if not self._key:
            return plaintext  # 未启用加密，透传

        iv = os.urandom(16)
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()

        # PKCS7 padding
        pad_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([pad_len] * pad_len)

        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return iv + ciphertext  # 前 16 字节为 IV

    def decrypt(self, ciphertext: bytes) -> bytes:
        """解密字节数据 → 返回 plaintext"""
        if not self._key:
            return ciphertext  # 未启用加密，透传

        if len(ciphertext) < 32:  # IV(16) + at least 1 block(16)
            raise ValueError("密文太短")

        iv = ciphertext[:16]
        data = ciphertext[16:]

        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        padded = decryptor.update(data) + decryptor.finalize()

        # PKCS7 unpad
        pad_len = padded[-1]
        if pad_len > 16 or pad_len == 0:
            raise ValueError("PKCS7 填充损坏")
        return padded[:-pad_len]

    @staticmethod
    def generate_key() -> str:
        """生成新密钥 → 保存到环境变量 DOC_ENCRYPTION_KEY"""
        key = os.urandom(32)
        return base64.b64encode(key).decode("ascii")


# 全局单例
doc_encryption = DocEncryption()
