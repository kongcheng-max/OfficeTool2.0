"""PDF 解析器 — 基于 PyMuPDF（支持流式批处理 + 页面范围 + 布局分析）"""

from typing import AsyncIterator, Callable, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from loguru import logger

from engine.parser.base import BaseParser, Chunk

# 流式批处理：每 N 页产出一次 chunks，降低内存峰值
DEFAULT_STREAM_BATCH = 20  # 每 20 页一批


class PDFParser(BaseParser):
    name = "pdf"
    supported_extensions = [".pdf"]
    supported_mime_types = ["application/pdf"]

    async def parse(
        self,
        file_path: str,
        original_filename: str,
        start_page: int = 1,
        max_pages: int = 0,
    ) -> List[Chunk]:
        """解析 PDF（全量，向后兼容）"""
        chunks: List[Chunk] = []
        async for batch in self.parse_stream(
            file_path, original_filename,
            start_page=start_page, max_pages=max_pages,
            batch_size=0,
        ):
            chunks.extend(batch)
        return chunks

    async def parse_stream(
        self,
        file_path: str,
        original_filename: str,
        start_page: int = 1,
        max_pages: int = 0,
        batch_size: int = DEFAULT_STREAM_BATCH,
    ) -> AsyncIterator[List[Chunk]]:
        """流式解析 PDF — 含布局分析（W9.2 / BUG-070）"""
        doc = fitz.open(file_path)
        total_pages = doc.page_count

        end_page = total_pages
        if max_pages > 0:
            end_page = min(start_page + max_pages - 1, total_pages)

        logger.info(
            f"PDF 流式解析: {original_filename} "
            f"(pages {start_page}-{end_page} / {total_pages}, batch={batch_size})"
        )

        # ── 布局分析阶段 1：收集所有页面文本（用于跨页页眉页脚检测）──
        all_page_texts: Dict[int, List[str]] = {}
        page_sizes: Dict[int, Tuple[float, float]] = {}
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num - 1]
            text = page.get_text("text")
            all_page_texts[page_num] = [
                ln.strip() for ln in text.split("\n") if ln.strip()
            ]
            rect = page.rect
            page_sizes[page_num] = (rect.width, rect.height)

        # ── 布局分析阶段 2：逐页解析（含布局过滤）──
        batch_chunks: List[Chunk] = []
        chunk_index = 0

        try:
            for page_num in range(start_page, end_page + 1):
                page = doc[page_num - 1]

                page_chunks = await self._parse_page_with_layout(
                    page, page_num, original_filename, chunk_index,
                    all_page_texts, page_sizes[page_num],
                )
                batch_chunks.extend(page_chunks)
                chunk_index += len(page_chunks)

                if batch_size > 0 and len(batch_chunks) >= batch_size:
                    yield batch_chunks
                    batch_chunks = []

            if batch_chunks:
                yield batch_chunks

        finally:
            doc.close()

    async def _parse_page_with_layout(
        self,
        page: fitz.Page,
        page_num: int,
        original_filename: str,
        base_chunk_index: int,
        all_page_texts: Dict[int, List[str]],
        page_size: Tuple[float, float],
    ) -> List[Chunk]:
        """解析单页 — 含布局分析过滤（BUG-070）"""
        chunks: List[Chunk] = []
        idx = base_chunk_index
        page_width, page_height = page_size

        # ── 布局分析：提取块 + 过滤页眉页脚 + 多栏排序 ──
        from engine.parser.layout import layout_analyzer

        blocks = layout_analyzer.extract_blocks_from_fitz(page)
        layout = layout_analyzer.analyze_page(
            page_num, blocks, page_width, page_height,
            global_page_texts=all_page_texts,
        )

        # 构建过滤后的正文文本（排除页眉页脚）
        header_footer_texts = {
            b.text for b in (layout.header_blocks + layout.footer_blocks)
        }
        body_texts = [b.text for b in layout.body_blocks
                      if b.text not in header_footer_texts]

        # 多栏页面：按列组织文本顺序
        if len(layout.columns) > 1:
            logger.debug(f"第{page_num}页检测到 {len(layout.columns)} 栏布局")
            column_texts = self._organize_by_columns(layout.body_blocks, layout.columns)
            body_text = "\n".join(column_texts)
        else:
            body_text = "\n".join(body_texts)

        if header_footer_texts:
            logger.debug(
                f"第{page_num}页过滤页眉页脚: "
                f"headers={len(layout.header_blocks)}, footers={len(layout.footer_blocks)}"
            )

        if body_text.strip():
            chunks.append(Chunk(
                content=body_text.strip(),
                metadata={
                    "page": page_num,
                    "source": original_filename,
                    "parser_name": self.name,
                    "chunk_index": idx,
                    "layout_columns": len(layout.columns),
                    "has_header_footer": bool(header_footer_texts),
                },
                chunk_type="text",
            ))
            idx += 1
        else:
            # 无正文（可能是纯扫描页）→ OCR 回退
            logger.info(f"第{page_num}页无正文文本，启用 OCR 回退")
            try:
                from engine.parser.ocr import OCRParser
                ocr = OCRParser()
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                ocr_chunks = await ocr.parse_image_bytes(
                    img_bytes, f"{original_filename}#page{page_num}"
                )
                for c in ocr_chunks:
                    c.metadata["ocr_fallback"] = True
                    c.metadata["page"] = page_num
                    c.metadata["source"] = original_filename
                    c.metadata["parser_name"] = self.name
                    c.metadata["chunk_index"] = idx
                    chunks.append(c)
                    idx += 1
            except Exception as e:
                logger.warning(f"OCR 回退失败 page={page_num}: {e}")

        # 表格检测与提取（带布局区域增强）
        tables = page.find_tables()
        for tb in tables:
            markdown_table = self._table_to_markdown(tb)
            if markdown_table.strip():
                chunks.append(Chunk(
                    content=markdown_table,
                    metadata={
                        "page": page_num,
                        "source": original_filename,
                        "is_table": True,
                        "parser_name": self.name,
                        "chunk_index": idx,
                    },
                    chunk_type="table",
                ))
                idx += 1

        # 布局检测到的额外表格区域（PyMuPDF 漏检的）
        for tx0, ty0, tx1, ty1 in layout.table_regions:
            # 避免与已检测表格重复
            already_covered = any(
                abs(tx0 - tb.bbox[0]) < 20 and abs(ty0 - tb.bbox[1]) < 20
                for tb in (tables or [])
            )
            if not already_covered:
                chunks.append(Chunk(
                    content=f"[疑似表格区域: {page_num}页, 位置({tx0:.0f},{ty0:.0f})-({tx1:.0f},{ty1:.0f})]",
                    metadata={
                        "page": page_num,
                        "source": original_filename,
                        "is_table": True,
                        "detected_by": "layout_analyzer",
                        "parser_name": self.name,
                        "chunk_index": idx,
                    },
                    chunk_type="table",
                ))
                idx += 1

        return chunks

    @staticmethod
    def _organize_by_columns(
        blocks: List,
        columns: List[Tuple[float, float]],
    ) -> List[str]:
        """多栏页面：按列分组文本，从左到右、从上到下排序"""
        col_texts: Dict[int, List[str]] = {i: [] for i in range(len(columns))}
        for b in blocks:
            x_center = (b.x0 + b.x1) / 2
            col_idx = 0
            min_dist = float("inf")
            for i, (cx0, cx1) in enumerate(columns):
                col_center = (cx0 + cx1) / 2
                dist = abs(x_center - col_center)
                if dist < min_dist:
                    min_dist = dist
                    col_idx = i
            col_texts[col_idx].append(b.text)

        ordered = []
        for i in sorted(col_texts.keys()):
            ordered.extend(col_texts[i])
        return ordered

    @staticmethod
    def _table_to_markdown(table) -> str:
        """将 PyMuPDF 表格转为 Markdown 格式"""
        try:
            data = table.extract()
            if not data:
                return ""
            lines = []
            # 表头
            header = data[0]
            lines.append("| " + " | ".join(str(c) if c else "" for c in header) + " |")
            lines.append("|" + "|".join("---" for _ in header) + "|")
            # 数据行
            for row in data[1:]:
                lines.append("| " + " | ".join(str(c) if c else "" for c in row) + " |")
            return "\n".join(lines)
        except Exception:
            return str(table)
