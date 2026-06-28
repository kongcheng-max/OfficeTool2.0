# BUG-027: EntityExtractor 全局单例 self._llm=None 导致 LLM 抽取永不执行

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | Week 6: 实体识别准确率 ≥70% |
| **发现方式** | 运行时测试 + 代码审查 |
| **状态** | Open |

## 现象
`entity_extractor.extract(text, use_llm=True)` 永远只走规则引擎，LLM 路径完全不触发。

## 根因
`extractor.py` 第 182 行创建全局单例时未传入 llm_client：
```python
entity_extractor = EntityExtractor()  # self._llm = None
```

第 76 行的守卫条件要求 `self._llm` 为真才进入 LLM 分支：
```python
if use_llm and self._llm:  # self._llm is None → 永远 False
    llm_entities = await self._llm_extract(text)
```

但 `_llm_extract()` 方法（第 124 行）实际上直接用 `LLMFactory.generate_with_fallback()`，并不需要 `self._llm`。守卫条件与实现不一致。

## 影响
- 法律术语 (TERM: "不可抗力"、"竞业限制"、"知识产权") 规则引擎无法识别 → 永远缺失
- 纯粹从 LLM 上下文推断的实体全部丢失
- Phase 2 要求实体识别 ≥70% 不可能达标（规则引擎无法覆盖术语和复杂场景）
- 实际上 Phase 2 KG 功能等于只跑了一半（同义反复的关系、术语实体全部缺位）

## 修复
将第 76 行的守卫条件去掉或改为始终调用：
```python
if use_llm:  # 不需要 self._llm，_llm_extract 内部直接用 LLMFactory
    llm_entities = await self._llm_extract(text)
```
