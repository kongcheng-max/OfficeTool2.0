"""查询改写 — 自动扩展/改写用户问题以提升召回率

Phase 3 W9.6: 通过 LLM 生成查询变体 + 规则回退，解决用户查询短/模糊/术语不匹配问题。
"""

import re
from typing import List, Optional

from loguru import logger


# ── 规则引擎：常见中文术语同义/扩展词典 ──

_SYNONYM_MAP: dict = {
    # 技术术语
    "AI": "人工智能",
    "ML": "机器学习",
    "NLP": "自然语言处理",
    "KG": "知识图谱",
    "RAG": "检索增强生成",
    "API": "接口",
    "SDK": "开发工具包",
    "SaaS": "软件即服务",
    "PaaS": "平台即服务",
    "IaaS": "基础设施即服务",
    "CI/CD": "持续集成 持续部署",
    "微服务": "微服务架构 服务拆分",
    "DDD": "领域驱动设计",
    "TDD": "测试驱动开发",
    "ORM": "对象关系映射",
    "MQ": "消息队列",
    "分布式": "分布式系统 分布式架构",
    "高并发": "高并发 高可用 高性能",
    "低代码": "低代码平台 零代码",
    "云原生": "云原生 容器化 Kubernetes",
    "DevOps": "开发运维 自动化运维",

    # 商业/法律术语
    "合同": "合同 协议 合约",
    "知识产权": "知识产权 著作权 专利 商标",
    "竞业": "竞业限制 竞业禁止 竞业协议",
    "违约金": "违约金 违约赔偿 违约责任",
    "不可抗力": "不可抗力 免责 自然灾害",
    "保密": "保密 商业秘密 保密义务",
    "仲裁": "仲裁 争议解决 诉讼",

    # 常见缩写
    "HR": "人力资源 人事",
    "PR": "公共关系 公关",
    "CEO": "首席执行官 总经理",
    "CFO": "首席财务官 财务总监",
    "CTO": "首席技术官 技术总监",
    "IPO": "上市 首次公开募股",
    "KPI": "关键绩效指标 考核指标",
    "OKR": "目标与关键结果",

    # 时间/数字
    "Q1": "第一季度 Q1季度",
    "FY": "财年 财政年度",
}


class QueryRewriter:
    """查询改写器 — LLM 主路径 + 规则引擎回退"""

    def __init__(self):
        self._use_llm = True  # LLM 可用则使用，不可用降级规则

    async def rewrite(
        self,
        query: str,
        max_variants: int = 3,
    ) -> List[str]:
        """生成查询变体列表

        Args:
            query: 用户原始查询
            max_variants: 最多生成的变体数

        Returns:
            查询变体列表（含原始查询），去重排序
        """
        variants = [query]  # 原始查询永远在第一位

        # 1. 规则引擎快速扩展
        rule_variants = self._rule_rewrite(query)
        for v in rule_variants:
            if v not in variants:
                variants.append(v)

        # 2. LLM 智能改写（优先，能捕捉上下文和意图）
        if self._use_llm:
            try:
                llm_variants = await self._llm_rewrite(query, max_variants)
                for v in llm_variants:
                    if v not in variants:
                        variants.append(v)
            except Exception as e:
                logger.warning(f"LLM 查询改写失败，仅用规则引擎: {e}")
                self._use_llm = False

        # 限制数量
        result = variants[:max_variants + 1]
        if len(result) > 1:
            logger.info(
                f"查询改写: '{query[:60]}' → {len(result)} variants: {result[1:]}"
            )
        return result

    def _rule_rewrite(self, query: str) -> List[str]:
        """规则引擎：词典匹配 + 缩写扩展"""
        variants = []

        # 缩写/同义词替换
        # BUG-071: \b 在中文前后行为不一致 → 改用显式中文边界匹配
        # 匹配: 字符串开头/结尾 | 空格 | 中文 | 标点
        _CHINESE_BOUNDARY = r'(?:^|(?<=[\s一-鿿，。；：！？、]))'
        _CHINESE_BOUNDARY_END = r'(?:$|(?=[\s一-鿿，。；：！？、]))'

        expanded = query
        for abbr, full in _SYNONYM_MAP.items():
            pattern = _CHINESE_BOUNDARY + re.escape(abbr) + _CHINESE_BOUNDARY_END
            if re.search(pattern, query, re.IGNORECASE):
                # 替换第一个匹配（lookaround 零宽，仅匹配 abbr 本身）
                expanded = re.sub(
                    pattern, full, expanded, count=1, flags=re.IGNORECASE,
                )
        if expanded != query:
            variants.append(expanded)

        # 纯中文：尝试关键词拆分重组
        if re.match(r'^[一-鿿\s]+$', query) and len(query) >= 4:
            # 去掉疑问词，生成关键词版本
            keywords = re.sub(r'(什么是|如何|怎样|怎么|哪些|为什么|请问|帮我|麻烦)', '', query).strip()
            if keywords and keywords != query:
                variants.append(keywords)

        return variants

    async def _llm_rewrite(self, query: str, max_variants: int) -> List[str]:
        """LLM 改写：生成语义等价的查询变体"""
        from engine.llm.factory import LLMFactory

        messages = [
            {"role": "system", "content": _LLM_REWRITE_SYSTEM},
            {"role": "user", "content": _LLM_REWRITE_USER.format(
                query=query, n=max_variants
            )},
        ]

        answer = await LLMFactory.generate_with_fallback(
            messages=messages,
            temperature=0.3,
        )

        # 解析 JSON 数组
        json_match = re.search(r'\[.*\]', answer, re.DOTALL)
        if json_match:
            import json
            try:
                variants = json.loads(json_match.group(0))
                if isinstance(variants, list):
                    return [v for v in variants if isinstance(v, str) and len(v) >= 2]
            except json.JSONDecodeError:
                pass

        return []


_LLM_REWRITE_SYSTEM = """你是一个搜索查询改写助手。你的任务是将用户的原始查询改写成 {n} 个不同的表达方式，以提高文档检索的召回率。

## 改写策略
1. **同义词替换**: 用行业标准术语替换口语化表达
2. **缩写展开**: 将缩写补全为全称（反之亦然）
3. **问题拆分**: 将复杂问题拆为更精准的关键词查询
4. **语义等价**: 用不同句式表达相同意图

## 输出格式
返回 JSON 字符串数组，不包含任何其他文字:
["变体1", "变体2", "变体3"]
"""

_LLM_REWRITE_USER = """原始查询: {query}

请生成 {n} 个改写变体（JSON 数组）:"""


# 全局单例
query_rewriter = QueryRewriter()
