# BUG-013: 前端重复目录结构 (frontend vs app/frontend)

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响 AC** | AC08 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
项目根目录存在两个前端目录：
- `E:\OfficeTool\frontend/` — 仅含 `package.json` 和 `package-lock.json`（空壳）
- `E:\OfficeTool\app\frontend/` — 实际的 React 应用代码

架构文档 (`02-系统架构设计.md`) 引用的是 `OfficeTool/frontend/`。

## 根因
可能在迭代中将前端代码移入 `app/` 目录，但遗留了旧目录。

## 影响
- 开发人员困惑实际工作目录
- IDE 可能错误索引空壳目录
- Dockerfile 复制上下文可能错误

## 修复建议
1. 删除空的 `E:\OfficeTool\frontend/` 目录
2. 更新文档中的前端路径引用
