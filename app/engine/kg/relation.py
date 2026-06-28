"""关系抽取 — 基于共现实体推断关系类型"""

import json
import re
from typing import Dict, List

from loguru import logger

# 关系类型定义
RELATION_TYPES = {
    "BELONGS_TO": "属于",
    "SIGNS": "签署",
    "OWNS": "拥有",
    "PART_OF": "组成部分",
    "RELATED_TO": "相关",
    "RESPONSIBLE_FOR": "负责",
    "HAPPENED_AT": "发生于",
    "INVOLVES": "涉及",
    "CONTRADICTS": "矛盾",
    "SUPERSEDES": "替代",
}


class RelationExtractor:
    """关系抽取器 — 共现分析 + LLM 语义推断"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    async def extract(
        self,
        text: str,
        entities: List[Dict],
        use_llm: bool = True,
    ) -> List[Dict]:
        """抽取实体间的关系

        Args:
            text: 原始文本
            entities: 已抽取的实体列表
            use_llm: 是否使用 LLM

        Returns:
            [{subject, predicate, object, confidence, evidence}, ...]
        """
        # 按实体在文本中出现位置排序
        entity_positions = []
        for ent in entities:
            entity_name = ent.get("normalized_name", ent["name"])
            for match in re.finditer(re.escape(entity_name), text):
                entity_positions.append({
                    "entity": ent,
                    "start": match.start(),
                    "end": match.end(),
                })
            # 也尝试匹配原始名称
            if entity_name != ent["name"]:
                for match in re.finditer(re.escape(ent["name"]), text):
                    # 避免重复添加
                    pos_key = match.start()
                    if not any(p["start"] == pos_key for p in entity_positions):
                        entity_positions.append({
                            "entity": ent,
                            "start": pos_key,
                            "end": match.end(),
                        })

        entity_positions.sort(key=lambda x: x["start"])

        relations = []
        used_triplets = set()  # subject|predicate|object 三元组去重

        def add_relation(subj, pred, obj, conf, evidence="", subj_type="", obj_type=""):
            """添加关系（按三元组去重）"""
            key = f"{subj}|{pred}|{obj}"
            if key not in used_triplets:
                used_triplets.add(key)
                relations.append({
                    "subject": subj,
                    "subject_type": subj_type,
                    "predicate": pred,
                    "object": obj,
                    "object_type": obj_type,
                    "confidence": conf,
                    "evidence": evidence,
                })

        # 1. 共现分析：距离 < 200 字符的实体对，标记为 RELATED_TO
        for i, a in enumerate(entity_positions):
            for j, b in enumerate(entity_positions[i + 1:], i + 1):
                distance = b["start"] - a["end"]
                if 0 < distance < 200:
                    # 提取中间文本作为证据
                    evidence = text[a["end"]:b["start"]].strip()[:200]
                    subj_name = a["entity"].get("normalized_name", a["entity"]["name"])
                    obj_name = b["entity"].get("normalized_name", b["entity"]["name"])
                    add_relation(
                        subj=subj_name,
                        pred="RELATED_TO",
                        obj=obj_name,
                        conf=max(0.3, 1.0 - distance / 200),
                        evidence=evidence,
                        subj_type=a["entity"].get("type", ""),
                        obj_type=b["entity"].get("type", ""),
                    )

        # 2. LLM 语义关系推断
        if use_llm and self._llm and len(entities) >= 2:
            try:
                llm_relations = await self._llm_extract_relations(text, entities)
                for rel in llm_relations:
                    subject = rel.get("subject", "")
                    predicate = rel.get("predicate", "RELATED_TO")
                    obj = rel.get("object", "")
                    # 尝试用标准化名称替换
                    subj_normalized = self._find_normalized_name(subject, entities)
                    obj_normalized = self._find_normalized_name(obj, entities)
                    add_relation(
                        subj=subj_normalized or subject,
                        pred=predicate,
                        obj=obj_normalized or obj,
                        conf=rel.get("confidence", 0.5),
                        evidence="",
                        subj_type="",
                        obj_type="",
                    )
            except Exception as e:
                logger.warning(f"LLM 关系抽取失败: {e}")

        logger.info(f"关系抽取完成: 共现 {len([r for r in relations if r.get('predicate') == 'RELATED_TO'])} 条, LLM 补充 {len(relations) - len([r for r in relations if r.get('predicate') == 'RELATED_TO'])} 条, 总计去重后 {len(relations)} 条")
        return relations

    @staticmethod
    def _find_normalized_name(name: str, entities: List[Dict]) -> str:
        """查找实体的标准化名称"""
        for ent in entities:
            if ent["name"] == name:
                return ent.get("normalized_name", name)
            if ent.get("normalized_name") == name:
                return name
        return ""

    async def _llm_extract_relations(
        self, text: str, entities: List[Dict]
    ) -> List[Dict]:
        """使用 LLM 抽取关系（使用 prompts 模块的标准接口）"""
        from engine.llm.factory import LLMFactory
        from engine.kg.prompts import get_relation_extraction_messages

        try:
            messages = get_relation_extraction_messages(entities, text[:2000])
            answer = await LLMFactory.generate_with_fallback(
                messages=messages,
                temperature=0.3,
            )
            json_match = re.search(r"\[.*\]", answer, re.DOTALL)
            if json_match:
                relations = json.loads(json_match.group(0))
                # 按三元组去重（LLM 可能返回重复结果）
                seen = set()
                unique = []
                for rel in relations:
                    key = f"{rel.get('subject', '')}|{rel.get('predicate', '')}|{rel.get('object', '')}"
                    if key not in seen:
                        seen.add(key)
                        unique.append(rel)
                logger.info(f"LLM 关系抽取: 原始 {len(relations)} 条, 去重后 {len(unique)} 条")
                return unique
        except Exception as e:
            logger.warning(f"LLM 关系抽取解析失败: {e}")

        return []


# 全局单例
relation_extractor = RelationExtractor()
