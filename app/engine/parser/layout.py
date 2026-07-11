"""文档布局分析 — 多栏识别、页眉页脚过滤、表格定位

Phase 3 W9.2: 增强 PDF/DOCX 文档的结构化解析能力。
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class TextBlock:
    """文本块的位置与内容信息"""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_num: int
    block_type: str = "text"  # "text" | "header" | "footer" | "table"


@dataclass
class LayoutInfo:
    """页面的布局分析结果"""
    page_num: int
    columns: List[Tuple[float, float]] = field(default_factory=list)  # [(x0, x1), ...]
    header_blocks: List[TextBlock] = field(default_factory=list)
    footer_blocks: List[TextBlock] = field(default_factory=list)
    body_blocks: List[TextBlock] = field(default_factory=list)
    table_regions: List[Tuple[float, float, float, float]] = field(default_factory=list)


class LayoutAnalyzer:
    """文档布局分析器

    功能:
      1. 多栏识别：按文本块 x 坐标聚类，识别多栏布局
      2. 页眉页脚过滤：检测页面间重复的页眉/页脚文本并标记
      3. 表格定位：基于文本块密集度和对齐特征定位表格区域
    """

    # 页眉/页脚区域阈值（页面高度的百分比）
    HEADER_RATIO = 0.10   # 上方 10%
    FOOTER_RATIO = 0.10   # 下方 10%

    # 多栏检测：文本块 x 坐标聚类的合并阈值（页面宽度的百分比）
    COLUMN_MERGE_RATIO = 0.05

    @staticmethod
    def extract_blocks_from_fitz(page: "fitz.Page") -> List[TextBlock]:
        """从 PyMuPDF 页面提取文本块位置信息

        Args:
            page: PyMuPDF Page 对象

        Returns:
            TextBlock 列表，含位置信息
        """
        import fitz
        blocks: List[TextBlock] = []

        # 使用 "dict" 模式获取详细的块信息
        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # 文本块
                bbox = block.get("bbox", [0, 0, 0, 0])
                text_parts = []
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_parts.append(span.get("text", ""))

                text = " ".join(text_parts).strip()
                if text:
                    blocks.append(TextBlock(
                        text=text,
                        x0=bbox[0], y0=bbox[1],
                        x1=bbox[2], y1=bbox[3],
                        page_num=-1,  # 由调用方填充
                    ))

        return blocks

    def analyze_page(
        self,
        page_num: int,
        blocks: List[TextBlock],
        page_width: float,
        page_height: float,
        global_page_texts: Optional[Dict[int, List[str]]] = None,
    ) -> LayoutInfo:
        """分析单页布局

        Args:
            page_num: 页码
            blocks: 该页的文本块列表
            page_width: 页面宽度
            page_height: 页面高度
            global_page_texts: {page_num: [text_line, ...]} 用于页眉页脚检测

        Returns:
            LayoutInfo 布局分析结果
        """
        # 填充页码
        for b in blocks:
            b.page_num = page_num

        info = LayoutInfo(page_num=page_num)

        # 1. 页眉页脚检测
        header_y = page_height * self.HEADER_RATIO
        footer_y = page_height * (1 - self.FOOTER_RATIO)

        # 全局页眉页脚过滤：多页重复出现的顶部/底部文本
        if global_page_texts:
            header_candidates, footer_candidates = self._find_repeating_regions(
                blocks, global_page_texts, header_y, footer_y  # BUG-072: footer_y 已是底部边界，不需再减
            )
            info.header_blocks = header_candidates
            info.footer_blocks = footer_candidates
            header_footer_texts = {
                b.text for b in (header_candidates + footer_candidates)
            }
            body_blocks = [b for b in blocks if b.text not in header_footer_texts]
        else:
            # 单页模式：仅按位置划分
            body_blocks = []
            for b in blocks:
                if b.y1 < header_end_y:
                    info.header_blocks.append(b)
                elif b.y0 > footer_start_y:
                    info.footer_blocks.append(b)
                else:
                    body_blocks.append(b)

        info.body_blocks = body_blocks

        # 2. 多栏识别
        if body_blocks:
            info.columns = self._detect_columns(body_blocks, page_width)

        # 3. 表格定位
        info.table_regions = self._detect_table_regions(blocks, page_width, page_height)

        return info

    def _find_repeating_regions(
        self,
        blocks: List[TextBlock],
        global_texts: Dict[int, List[str]],
        header_end_y: float,
        footer_start_y: float,  # BUG-072: 底部边界起始位置，不是偏移量
    ) -> Tuple[List[TextBlock], List[TextBlock]]:
        """检测跨页面重复的页眉/页脚文本"""
        # 收集所有页面的顶部和底部文本
        all_top_texts: List[str] = []
        all_bottom_texts: List[str] = []
        for texts in global_texts.values():
            # 取头尾两个 block 作为候选
            if len(texts) >= 1:
                all_top_texts.append(texts[0])
            if len(texts) >= 2:
                all_bottom_texts.append(texts[-1])

        # 选出高频出现的文本（至少出现 2 次）
        top_counter = Counter(all_top_texts)
        bottom_counter = Counter(all_bottom_texts)

        repeating_top = {t for t, c in top_counter.items() if c >= 2 and len(t) < 200}
        repeating_bottom = {t for t, c in bottom_counter.items() if c >= 2 and len(t) < 200}

        headers = [b for b in blocks if b.text in repeating_top or b.y1 < header_end_y]
        footers = [b for b in blocks if b.text in repeating_bottom or b.y0 > footer_start_y]

        return headers, footers

    def _detect_columns(
        self,
        blocks: List[TextBlock],
        page_width: float,
    ) -> List[Tuple[float, float]]:
        """检测多栏布局：按文本块 x 中心点聚类

        Returns:
            [(x0_min, x1_max), ...] 每栏的 x 范围
        """
        if len(blocks) < 3:
            return [(0, page_width)]

        # 取 x 中心点
        x_centers = sorted((b.x0 + b.x1) / 2 for b in blocks if b.x1 - b.x0 > 10)

        if len(x_centers) < 3:
            return [(0, page_width)]

        # 简单聚类：相邻中心点间距 > 页面宽度 15% 视为不同栏
        merge_threshold = page_width * self.COLUMN_MERGE_RATIO
        clusters: List[List[float]] = [[x_centers[0]]]

        for xc in x_centers[1:]:
            if xc - clusters[-1][-1] > merge_threshold:
                clusters.append([xc])
            else:
                clusters[-1].append(xc)

        # 过滤过小的聚类（< 2 个块）
        clusters = [c for c in clusters if len(c) >= 2]

        if len(clusters) <= 1:
            return [(0, page_width)]

        # 构建每栏的 x 范围
        columns = []
        # 为每栏找对应的 block x 范围
        for cluster in clusters:
            c_min = min(clus - merge_threshold for clus in cluster)
            c_max = max(clus + merge_threshold for clus in cluster)
            columns.append((max(0, c_min), min(page_width, c_max)))

        logger.debug(f"多栏检测: {len(columns)} 栏, 列范围={columns}")
        return columns

    def _detect_table_regions(
        self,
        blocks: List[TextBlock],
        page_width: float,
        page_height: float,
    ) -> List[Tuple[float, float, float, float]]:
        """基于文本块密集度检测表格区域

        表格特征:
        - 文本块密度高（间距小）
        - 列对齐性强
        - 通常含数字/短文本

        Returns:
            [(x0, y0, x1, y1), ...] 表格区域边界
        """
        if len(blocks) < 4:
            return []

        regions = []
        # 按 y 坐标排序，检测密集区域
        blocks_sorted = sorted(blocks, key=lambda b: (b.y0, b.x0))
        dense_groups = []
        current_group = [blocks_sorted[0]]

        for b in blocks_sorted[1:]:
            prev = current_group[-1]
            # y 间距小 + 文本短 → 可能是表格行
            y_gap = b.y0 - prev.y1
            if y_gap < 10 and len(b.text) < 100:
                current_group.append(b)
            else:
                if len(current_group) >= 3:
                    dense_groups.append(current_group)
                current_group = [b]

        if len(current_group) >= 3:
            dense_groups.append(current_group)

        for group in dense_groups:
            x0 = min(b.x0 for b in group) - 5
            y0 = min(b.y0 for b in group) - 3
            x1 = max(b.x1 for b in group) + 5
            y1 = max(b.y1 for b in group) + 3
            regions.append((x0, y0, x1, y1))

        return regions


# 全局单例
layout_analyzer = LayoutAnalyzer()
