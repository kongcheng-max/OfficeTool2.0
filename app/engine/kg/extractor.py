"""实体抽取 — LLM 语义抽取 + 规则引擎辅助"""

import json
import re
from typing import Dict, List, Optional

from loguru import logger

# 实体类型
ENTITY_TYPES = ["PERSON", "ORG", "DATE", "MONEY", "LOCATION", "TERM"]

# 规则引擎 — 正则模式（无需 LLM，快速提取结构化实体）
RULE_PATTERNS: Dict[str, List[str]] = {
    "DATE": [
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?",
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        r"\d{2}[-/]\d{1,2}[-/]\d{1,2}",
    ],
    "MONEY": [
        r"(?:¥|￥|CNY|USD|\$)\s*[\d,]+\.?\d*\s*(?:万|亿|元|美元|元人民币)?",
        r"[\d,]+\.?\d*\s*(?:万元|亿元|元|美元|人民币)",
    ],
    "PERSON": [
        # 带角色标注前缀的姓名（高置信度）
        r"(?:甲方|乙方|法定代表人|签字人|负责人|联系人|法人|授权代表|委托代理)[：人:]\s*([一-鿿]{2,4})",
    ],
    "ORG": [
        r"([一-鿿]{2,30}(?:公司|集团|有限(?:责任)?公司|银行|事务所|机构|中心|部门))",
    ],
    "LOCATION": [
        # 完整地址（省市区街道+门牌号）
        r"[一-鿿]{2,10}(?:省|自治区|市|县|区|镇|乡|街道|路|街|巷|弄)[一-鿿\d]*号?",
        # 城市名模式（以"市"结尾）
        r"[一-鿿]{2,10}市",
        # 省份/直辖市
        r"[一-鿿]{2,10}(?:省|自治区|特别行政区)",
        # 国家名
        r"(?:中国|美国|日本|韩国|英国|法国|德国|俄罗斯|加拿大|澳大利亚|新加坡|马来西亚|泰国|越南|印度)",
    ],
}


class EntityExtractor:
    """实体抽取器 — 规则优先 + LLM 补充"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def extract(
        self,
        text: str,
        use_llm: bool = True,
    ) -> List[Dict]:
        """从文本中抽取实体

        Args:
            text: 待抽取文本
            use_llm: 是否使用 LLM 补充

        Returns:
            [{name, type, normalized_name, source, confidence, evidence}, ...]
        """
        entities: Dict[str, Dict] = {}  # name|type → entity 去重

        # 1. 规则引擎快速提取
        self._apply_rule_patterns(text, entities)

        # 2. LLM 语义抽取（补充规则漏掉的实体，尤其是 TERM 法律术语）
        # 短文档且有大量规则结果时也需走 LLM，否则 TERM 实体永远缺失
        if use_llm:
            try:
                llm_entities = await self._llm_extract(text)
                for ent in llm_entities:
                    ent_name = ent["name"]
                    ent_type = ent.get("type", "TERM")
                    # 使用标准化名称进行去重
                    normalized = ent.get("normalized_name", ent_name)
                    key = f"{normalized}|{ent_type}"
                    if key not in entities:
                        entities[key] = {
                            "name": ent_name,
                            "normalized_name": normalized,
                            "type": ent_type,
                            "source": "llm",
                            "confidence": ent.get("confidence", 0.7),
                            "evidence": ent.get("evidence", ""),
                        }
            except Exception as e:
                logger.warning(f"LLM 实体抽取失败: {e}")

        # 3. 实体标准化（对规则引擎和 LLM 的实体统一做标准化）
        # BUG-027 修复: _normalize_entities() 内部直接调 LLMFactory，不需要 self._llm
        if use_llm and entities:
            try:
                await self._normalize_entities(entities)
            except Exception as e:
                logger.warning(f"实体标准化失败: {e}")

        return list(entities.values())

    # BUG-030: 常见连词/介词前缀，ORG 匹配时需剥离
    _ORG_PREFIX_STRIP = re.compile(
        r"^(?:与|及|和|的|某|该|上述|前述|以下|以上|本|此|各|或|以及|及其|及其|连同)"
    )
    # BUG-028: 已知的城市名后缀列表（市结尾但非地址的常见情况）
    _KNOWN_CITIES = {
        "北京市", "上海市", "天津市", "重庆市",
        "深圳市", "广州市", "杭州市", "成都市", "武汉市", "南京市",
        "西安市", "郑州市", "苏州市", "东莞市", "青岛市", "长沙市",
        "大连市", "沈阳市", "厦门市", "合肥市", "福州市", "宁波市",
    }

    def _apply_rule_patterns(self, text: str, entities: Dict[str, Dict]) -> None:
        """将规则引擎正则匹配填入 entities 字典（原地修改）

        含后处理: BUG-030 ORG 前缀剥离, BUG-028 LOCATION/ORG 子串去重
        """
        for ent_type, patterns in RULE_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    name = match.group(0).strip()
                    if len(name) < 2:
                        continue

                    # --- BUG-030: ORG 前缀剥离 ---
                    if ent_type == "ORG":
                        # 捕获组优先（PERSON 正则等）
                        if match.lastindex and match.lastindex >= 1:
                            name = match.group(1).strip()
                        else:
                            name = self._ORG_PREFIX_STRIP.sub("", name).strip()
                        # 无论哪个分支，都要对结果做前缀剥离
                        name = self._ORG_PREFIX_STRIP.sub("", name).strip()
                        if len(name) < 4:  # 剥离后太短则丢弃
                            continue

                    # --- PERSON 捕获组提取 ---
                    if ent_type == "PERSON" and match.lastindex and match.lastindex >= 1:
                        name = match.group(1).strip()

                    key = f"{name}|{ent_type}"
                    if key not in entities:
                        entities[key] = {
                            "name": name,
                            "normalized_name": name,
                            "type": ent_type,
                            "source": "rule",
                            "confidence": 0.9,
                            "evidence": "",
                        }

        # --- BUG-028: LOCATION 被 ORG 包含时，丢弃 LOCATION ---
        org_names = {v["name"] for k, v in entities.items() if v["type"] == "ORG"}
        loc_keys_to_remove = []
        for key, ent in entities.items():
            if ent["type"] == "LOCATION":
                loc_name = ent["name"]
                for org_name in org_names:
                    # 如果 LOCATION 是 ORG 的真前缀子串（如 "深圳市" 在 "深圳市腾讯..." 中）
                    if loc_name != org_name and org_name.startswith(loc_name):
                        loc_keys_to_remove.append(key)
                        logger.debug(
                            f"BUG-028 后处理: 丢弃 LOCATION '{loc_name}' "
                            f"(被 ORG '{org_name}' 包含)"
                        )
                        break
                # 额外检查: 纯"X市"必须是已知城市名才保留
                if ent["type"] == "LOCATION" and key not in loc_keys_to_remove:
                    if re.match(r"^[一-鿿]{2,6}市$", loc_name):
                        if loc_name not in self._KNOWN_CITIES:
                            loc_keys_to_remove.append(key)
                            logger.debug(
                                f"BUG-028 后处理: 丢弃非城市 'X市' LOCATION '{loc_name}'"
                            )

        for key in loc_keys_to_remove:
            del entities[key]

    async def _llm_extract(self, text: str) -> List[Dict]:
        """使用 LLM 抽取实体（使用 prompts 模块的标准接口）"""
        from engine.llm.factory import LLMFactory
        from engine.kg.prompts import get_entity_extraction_messages

        try:
            messages = get_entity_extraction_messages(text[:2000])
            answer = await LLMFactory.generate_with_fallback(
                messages=messages,
                temperature=0.3,
            )
            # 提取 JSON 部分
            json_match = re.search(r"\[.*\]", answer, re.DOTALL)
            if json_match:
                entities = json.loads(json_match.group(0))
                # 为没有 normalized_name 的实体设置默认值
                for ent in entities:
                    if "normalized_name" not in ent:
                        ent["normalized_name"] = ent.get("name", "")
                return entities
        except Exception as e:
            logger.warning(f"LLM 实体抽取解析失败: {e}")

        return []

    async def _normalize_entities(self, entities: Dict[str, Dict]) -> None:
        """对已抽取实体进行标准化（调用 prompts 接口）"""
        from engine.llm.factory import LLMFactory
        from engine.kg.prompts import get_entity_normalization_messages

        # 组装实体列表用于标准化
        entity_list = []
        for key, ent in entities.items():
            entity_list.append({"name": ent["name"], "type": ent["type"]})

        if not entity_list:
            return

        try:
            messages = get_entity_normalization_messages(entity_list)
            answer = await LLMFactory.generate_with_fallback(
                messages=messages,
                temperature=0.2,
            )
            # 提取 JSON 对象
            json_match = re.search(r"\{.*\}", answer, re.DOTALL)
            if json_match:
                name_map = json.loads(json_match.group(0))
                # 应用标准化映射到实体
                for key, ent in entities.items():
                    original = ent["name"]
                    if original in name_map:
                        ent["normalized_name"] = name_map[original]
        except Exception as e:
            logger.warning(f"实体标准化解析失败: {e}")


# 全局单例
entity_extractor = EntityExtractor()
