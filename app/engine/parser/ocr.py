"""OCR 图片解析器 — 基于 PaddleOCR / Tesseract

触发场景:
- 图片文件 (.jpg/.png/.tiff/.bmp)
- PDF 扫描件无文字层时兜底
- DOCX/PPTX 嵌入图片导出后 OCR
"""

import os
from typing import List

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

    def _lazy_load_ocr(self):
        """延迟加载 OCR 引擎"""
        if self._ocr is not None:
            return

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
            return
        except ImportError:
            pass

        # 降级 Tesseract
        try:
            import pytesseract
            from PIL import Image
            self._ocr = {"tesseract": pytesseract, "Image": Image}
            self._ocr_type = "tesseract"
            return
        except ImportError:
            pass

        self._ocr_type = None

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
            # 无可用的 OCR 引擎，返回空
            return []

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
