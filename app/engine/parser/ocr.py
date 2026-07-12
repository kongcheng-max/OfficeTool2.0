"""OCR 图片解析器 — 基于 PaddleOCR / Tesseract

触发场景:
- 图片文件 (.jpg/.png/.tiff/.bmp)
- PDF 扫描件无文字层时兜底
- DOCX/PPTX 嵌入图片导出后 OCR
"""

import os
import shutil
from typing import List

from loguru import logger

from engine.parser.base import BaseParser, Chunk


class OCRParser(BaseParser):
    """图片 OCR 解析器

    优先使用 PaddleOCR（中文识别最佳），
    降级为 Tesseract（轻量备选）。
    """

    name = "ocr"
    supported_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"]
    supported_mime_types = [
        "image/jpeg",
        "image/png",
        "image/bmp",
        "image/tiff",
        "image/webp",
    ]

    def __init__(self):
        self._ocr = None
        self._ocr_type = None  # "paddle" | "tesseract" | None
        self._checked_availability = False  # 只做一次环境检测

    def _lazy_load_ocr(self):
        """延迟加载 OCR 引擎 — 含前置环境检测，快速跳过无效链路"""
        if self._ocr is not None:
            return
        if self._ocr_type is None and self._checked_availability:
            return  # 已确认两者都不可用，不再重复检测

        # 优先尝试 PaddleOCR
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang="ch",
                use_gpu=False,
                show_log=False,
            )
            self._ocr_type = "paddle"
            self._checked_availability = True
            logger.info("OCR 引擎: PaddleOCR 已就绪")
            return
        except ImportError:
            logger.debug("PaddleOCR 未安装")
        except Exception as e:
            logger.warning(f"PaddleOCR 加载失败: {e}")

        # 降级 Tesseract — 前置检测系统级二进制
        tesseract_bin = shutil.which("tesseract")
        if not tesseract_bin:
            logger.warning("Tesseract 系统二进制未安装，OCR 不可用")
            self._ocr_type = None
            self._checked_availability = True
            return

        try:
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = tesseract_bin
            self._ocr = {"tesseract": pytesseract, "Image": Image}
            self._ocr_type = "tesseract"
            self._checked_availability = True
            logger.info(f"OCR 引擎: Tesseract 已就绪 ({tesseract_bin})")
            return
        except ImportError:
            logger.debug("pytesseract 或 Pillow 未安装")
        except Exception as e:
            logger.warning(f"Tesseract 加载失败: {e}")

        self._ocr_type = None
        self._checked_availability = True

    async def parse_image_bytes(self, img_bytes: bytes, source_name: str) -> List[Chunk]:
        """从内存中的图片字节进行 OCR（PDF 扫描页回退 / 嵌入图片等场景）"""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        try:
            return await self.parse(tmp_path, source_name)
        finally:
            os.unlink(tmp_path)

    async def parse(self, file_path: str, original_filename: str) -> List[Chunk]:
        self._lazy_load_ocr()

        if self._ocr_type == "paddle":
            return await self._parse_paddle(file_path, original_filename)
        elif self._ocr_type == "tesseract":
            return await self._parse_tesseract(file_path, original_filename)
        else:
            # BUG-063: OCR 不可用时抛出明确错误，避免静默返回空 chunks
            raise RuntimeError(
                "OCR 引擎不可用：PaddleOCR 和 Tesseract 均未安装。"
                "图片/扫描 PDF 无法解析。请安装: pip install paddleocr pytesseract Pillow"
            )

    async def _parse_paddle(self, file_path: str, original_filename: str) -> List[Chunk]:
        """PaddleOCR 解析"""
        result = self._ocr.ocr(file_path, cls=True)

        if not result or not result[0]:
            return []

        lines = []
        confidences = []
        for line_info in result[0]:
            text = line_info[1][0]
            confidence = line_info[1][1]
            if text.strip():
                lines.append(text.strip())
                confidences.append(confidence)

        if not lines:
            return []

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return [Chunk(
            content="\n".join(lines),
            metadata={
                "source": original_filename,
                "parser_name": self.name,
                "ocr": True,
                "ocr_engine": "paddle",
                "ocr_confidence": round(avg_confidence, 4),
                "chunk_index": 0,
            },
            chunk_type="text",
        )]

    async def _parse_tesseract(self, file_path: str, original_filename: str) -> List[Chunk]:
        """Tesseract OCR 解析"""
        img = self._ocr["Image"].open(file_path)
        text = self._ocr["tesseract"].image_to_string(img, lang="chi_sim+eng")

        if not text.strip():
            return []

        return [Chunk(
            content=text.strip(),
            metadata={
                "source": original_filename,
                "parser_name": self.name,
                "ocr": True,
                "ocr_engine": "tesseract",
                "chunk_index": 0,
            },
            chunk_type="text",
        )]
