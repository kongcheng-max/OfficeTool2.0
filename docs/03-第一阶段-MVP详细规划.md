# 03 — 第一阶段 · MVP 详细规划 (启明)

> **版本**: v3.0 | **日期**: 2026-06-27 | **周期**: 第 1-4 周 | **代号**: 启明 | **状态**: ✅ 已完成
> **关联**: [PRD](./01-产品需求文档(PRD).md) | [架构设计](./02-系统架构设计.md) | [二期规划](./04-第二阶段-高级功能详细规划.md)
>
> ℹ️ **组织说明**: 本文档为历史工作记录。第一、二阶段采用六部门架构（PM/BE/FE/AI/QA/Ops）。自 2026-07-11 起组织架构调整为三部门（产品部/研发部/测试部），详见 [README](./README.md)。

---

## 阶段目标

**核心链路跑通：用户上传文档 → 自动解析索引 → 自然语言提问 → LLM 返回精准答案。**

交付一个可完整演示的 Web 应用。

### 参与部门

| 部门 | 代号 | 本阶段角色 | 投入 |
|------|------|-----------|------|
| 产品部 | **PM** | 需求答疑、每日站会、验收 | 🟢 全程 |
| 后端开发 | **BE** | FastAPI + 解析引擎 + RAG管道 | 🟢 全程 |
| 前端开发 | **FE** | React 界面 + 联调 | 🟢 全程 |
| AI/算法 | **AI** | Embedding选型、LLM网关、Prompt设计 | 🟢 W3-4 |
| 测试 | **QA** | MVP验收测试 | 🟡 W4 |
| 运维 | **Ops** | Docker开发环境 + CI/CD | 🟡 W1, W4 |

---

## Week 1: 项目骨架搭建 (Day 1-5)

### W1D1-D2: 开发环境与项目初始化

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 1.1 | FastAPI 项目初始化，目录结构创建 | `backend/` 骨架、`main.py`、`pyproject.toml` | **BE** |
| 1.2 | React 项目初始化 (Vite + Ant Design + TS) | `frontend/` 骨架、`vite.config.ts` | **FE** |
| 1.3 | PostgreSQL + Redis + MinIO Docker 配置 | `docker-compose.yml` 开发环境 | **BE** + Ops |
| 1.4 | Alembic 数据库迁移框架配置 | `alembic/` 初始化 | **BE** |
| 1.5 | ESLint + Prettier + pre-commit 配置 | 代码规范工具链 | **BE** + FE |

### W1D3-D5: 基础设施实现

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 1.6 | SQLAlchemy 模型：User, KnowledgeBase, Document | `models/` 三个核心模型 | **BE** |
| 1.7 | 用户注册/登录 API (bcrypt + JWT) | `api/auth.py`、`services/user_service.py` | **BE** |
| 1.8 | 前端登录页 + 基础路由 + axios 封装 | `Login.tsx`、`api/` 目录 | **FE** |
| 1.9 | 全局配置模块 (pydantic-settings) | `core/config.py` — YAML 配置驱动 | **BE** |
| 1.10 | 全局异常处理 + 统一响应格式 | `{code, message, data}` 中间件 | **BE** |

**Week 1 验收标准**:
- ✅ Docker Compose 启动 PG + Redis + MinIO
- ✅ 项目能通过 `uvicorn main:app` 启动
- ✅ `POST /api/v1/auth/register` + `/login` 可用
- ✅ 前端登录页可访问、能获取 Token

---

## Week 2: 文档解析引擎 (Day 6-10)

### W2D1-D3: 解析器框架 + 前三种格式

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 2.1 | BaseParser 抽象基类 + ParserRegistry 注册中心 | `engine/parser/base.py`、`registry.py` | **BE** |
| 2.2 | PDFParser (PyMuPDF)：文字+表格提取 | `engine/parser/pdf.py` | **BE** |
| 2.3 | DOCXParser (python-docx)：段落+表格+样式 | `engine/parser/docx.py` | **BE** |
| 2.4 | TextParser (TXT/MD)：纯文本/Markdown | `engine/parser/text.py` | **BE** |

### W2D4-D5: 后两种格式 + 异步任务

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 2.5 | XLSXParser (openpyxl)：表格数据提取 | `engine/parser/xlsx.py` | **BE** |
| 2.6 | Celery 配置 + 文档解析异步任务 | `tasks/parse.py` | **BE** |
| 2.7 | API：上传文档 (multipart/form-data) → MinIO → Celery | `api/document.py`、`services/document_service.py` | **BE** |
| 2.8 | 前端文档上传组件 (拖拽 + 进度条) | `components/DocumentUpload.tsx` | **FE** |

**Week 2 验收标准**:
- ✅ 5 种格式（PDF/DOCX/XLSX/TXT/MD）解析器全部就绪
- ✅ 上传任一格式文件 → Celery 异步解析 → 返回 Chunk 列表
- ✅ 前端支持拖拽上传并显示进度
- ✅ 单页 PDF 解析 ≤ 10 秒

---

## Week 3: RAG 管道搭建 (Day 11-15)

### W3D1-D3: 分块 → 向量化 → 存储

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 3.1 | LangChain TextSplitter 集成（RecursiveChineseSplitter） | `engine/rag/splitter.py` | **BE** |
| 3.2 | Embedding 模块封装（先集成 text2vec-large-chinese） | `engine/rag/embedder.py` | **AI** + BE |
| 3.3 | Milvus 连接 + Collection 创建 + 写入 | `engine/rag/vector_store.py` | **BE** |
| 3.4 | Embedding 异步任务：解析完成 → 自动分块 → Embedding → 写入 Milvus | `tasks/embed.py` | **BE** |

### W3D4-D5: 检索 + LLM 集成

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 3.5 | 向量相似检索器（Milvus ANN Search Top-K） | `engine/rag/retriever.py` | **BE** |
| 3.6 | LLM 网关抽象层 + 通义千问适配器 | `engine/llm/base.py`、`tongyi.py`、`factory.py` | **AI** + BE |
| 3.7 | Prompt 模板：System + Context + Question | `engine/rag/prompt.py` | **AI** |
| 3.8 | 问答服务编排：检索 → 构建 Prompt → LLM 生成 → 返回 | `services/qa_service.py` | **BE** + AI |

**Week 3 验收标准**:
- ✅ 文档上传后 → 自动分块 → Embedding → 存入 Milvus（全自动化）
- ✅ 向知识库提问 → 检索 Top-K 相关块 → LLM 生成答案
- ✅ 端到端延迟 ≤ 10 秒（P95）
- ✅ 答案与文档内容相关（人工抽检）

---

## Week 4: 前端完善 + 联调 + 演示就绪 (Day 16-20)

### W4D1-D3: 核心前端页面

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 4.1 | 对话问答界面（Chat 组件 + Markdown 渲染 + SSE 流式） | `pages/Chat/` | **FE** |
| 4.2 | 知识库管理界面（列表、创建、删除） | `pages/KnowledgeBase/` | **FE** |
| 4.3 | 文档列表页面（知识库内文档浏览、搜索、删除） | `pages/Documents/` | **FE** |
| 4.4 | Dashboard 首页（KB 概览、最近文档、统计卡片） | `pages/Dashboard.tsx` | **FE** |

### W4D4-D5: 联调与打磨

| 任务 | 内容 | 产出物 | 负责人 |
|------|------|--------|--------|
| 4.5 | 前后端全链路联调 → 修复 Bug | 全链路可用 | **BE** + FE |
| 4.6 | SSE 流式问答调通 | 前端逐字展示 | **BE** + FE |
| 4.7 | 错误处理与提示（上传失败、解析失败、LLM 超时） | 友好错误提示 | **BE** + FE |
| 4.8 | Docker Compose 一键启动全栈 | `docker-compose.yml` | **Ops** + BE |
| 4.9 | MVP 演示 Checklist 准备 + 验收 | 演示脚本 + 验收报告 | **PM** + QA |

---

## MVP 交付清单

| 编号 | 功能 | 验证方式 |
|------|------|---------|
| ✅ | 用户注册/登录 | Web 页面操作 |
| ✅ | 创建/删除知识库 | Web 页面操作 |
| ✅ | 上传 PDF/DOCX/XLSX/TXT/MD 文档 | 拖拽上传 |
| ✅ | 文档自动解析 → Embedding → Milvus 索引 | 上传后查看状态 |
| ✅ | 知识库内自然语言提问 | 对话界面 |
| ✅ | LLM 基于文档生成答案 | 答案相关性 ≥80% |
| ✅ | 答案包含来源引用 | 显示引用文档和页码 |
| ✅ | 多知识库数据隔离 | 切换 KB 问答结果不同 |
| ✅ | Docker Compose 一键启动 | `docker compose up -d` |

## MVP 不包含（留待第二阶段）

- ❌ PPTX / CSV / JSON / HTML 解析
- ❌ OCR 图片识别
- ❌ BM25 关键词检索
- ❌ 知识图谱（实体抽取、Neo4j）
- ❌ 混合检索 RRF 融合
- ❌ 多轮对话
- ❌ 批量上传 / 压缩包导入
- ❌ 标签系统
- ❌ RBAC 权限控制

---

> 📎 **关联**: [二期规划](./04-第二阶段-高级功能详细规划.md) — MVP 之后的下一个阶段
