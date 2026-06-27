# BUG-018: 解析器双重注册 (ParserRegistry)

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响 AC** | AC01 |
| **发现方式** | 代码审查 + 运行时测试 |
| **状态** | Open |

## 现象
`ParserRegistry` 中每个解析器被注册了两次，`get_all()` 返回 10 个对象（预期 5 个）。

## 根因
解析器从两个位置同时注册：

1. `app/engine/parser/__init__.py:10-14` — 模块加载时自动注册
   ```python
   ParserRegistry.register(PDFParser())
   ParserRegistry.register(DOCXParser())
   ...
   ```

2. `app/engine/parser/registry.py:10-16` 的 `register_all_parsers()` — 被 `tasks/parse.py:17` 调用
   ```python
   register_all_parsers()
   ```

3. 另有 `main.py:14` 的 `import engine.parser` 触发 `__init__.py` 的自动注册

## 影响
- `find_for()` 返回第一个匹配的解析器，功能不受影响
- 内存中有冗余解析器实例
- 代码气味：两个注册路径增加了维护负担

## 修复建议
统一注册入口：移除 `__init__.py` 中的自动注册，只保留显式的 `register_all_parsers()` 调用。
