# OfficeTool v2.0 GA 发布说明

> **发布日期**: 2026-07-11 | **代号**: 瑶光 | **版本**: v2.0.0

---

## 概述

OfficeTool v2.0 是首个生产就绪（GA）版本。经过三个阶段的迭代开发，系统已具备企业级私有部署所需的**性能、安全、稳定性**，可正式投入生产环境使用。

### 产品定位

OfficeTool 是一套**私有化部署**的企业文档智能解析与问答系统，利用 LLM + RAG + 知识图谱技术，让企业的每一份文档都成为可对话的知识。

---

## 核心能力

### 📄 多格式文档解析
支持 **11 种格式**：PDF / DOCX / XLSX / PPTX / TXT / MD / CSV / JSON / HTML / XML / 图片(OCR)

- 大文件流式解析（100MB+ PDF 不溢出）
- 文档布局分析（多栏识别、页眉页脚过滤）
- OCR 双引擎（PaddleOCR + Tesseract）

### 🧠 混合智能检索
**三路并行 + RRF 融合 + Cross-encoder 精排**

```
向量检索(Milvus) ─┐
BM25 检索(ES)   ─┼─ RRF 融合 ─ Cross-encoder ─ 精准结果
图谱检索(Neo4j) ─┘
```

- 查询改写自动扩展召回
- LLM 问答缓存（相同问题秒返回）

### 🕸️ 知识图谱
- 自动抽取 6 类实体 + 9 种关系
- G6 交互式可视化
- **NL2Cypher**：自然语言直接查询图谱

### 💬 智能问答
- 答案溯源（引用原文 + 页码）
- 多轮对话（上下文记忆 + 代词消解）
- 流式 SSE 输出

### 🔒 企业级安全
- **RBAC 三角色**：admin / editor / viewer
- **操作审计**：全量记录，仅 admin 可查
- **API 限流**：Token Bucket，超限 429
- **AES-256 加密**：可选的文档原文加密

### 🚀 一键部署
- **Docker Compose 生产编排**：10 服务全量一键启动
- **轻量部署**：单机 SQLite 模式，无需 Docker

---

## 系统要求

| 环境 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核+ |
| 内存 | 16 GB | 32 GB+ |
| 磁盘 | 50 GB | 200 GB+ SSD |
| GPU（可选） | — | NVIDIA 8GB+ VRAM（加速 OCR/Embedding/Reranker） |
| 操作系统 | Ubuntu 20.04+ / CentOS 8+ / Windows 11 |

### Docker 模式依赖
- Docker 24.0+ & Docker Compose v2
- 端口：80(Nginx), 5432(PG), 6379(Redis), 9000(MinIO), 9200(ES), 7474/7687(Neo4j), 19530(Milvus)

### 轻量模式依赖
- Python 3.11+
- Node.js 18+
- SQLite（内嵌，无需安装）

---

## 快速开始

### Docker 生产部署（推荐）

```bash
# 1. 克隆仓库
git clone <repo-url> && cd OfficeTool/app

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API Key 等必要配置

# 3. 一键启动
docker compose -f docker-compose.prod.yml up -d

# 4. 验证
curl http://localhost/api/health
# → {"status": "ok"}

# 5. 浏览器访问
open http://localhost
```

### 轻量部署

```bash
cd OfficeTool
bash deploy/deploy.sh
```

---

## 从 Beta 升级

如果你正在运行 v1.0.0-beta：

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 数据库迁移
docker exec officetool-app alembic upgrade head

# 3. 重启服务
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 已知限制

- OCR 在 Docker 环境需单独安装 Tesseract 系统二进制（`apt install tesseract-ocr-chi-sim`）
- Cross-encoder 精排需安装 FlagEmbedding（`pip install FlagEmbedding`），不可用时自动降级
- 移动端仅支持响应式 Web，无原生 App
- 不支持在线文档编辑/实时协作

---

## 下一步计划（v2.1+）

- TLS/HTTPS 证书自动化
- 数据备份/恢复脚本
- 移动端响应式适配优化
- SSO/LDAP 企业身份集成
- 多语言界面（英文/日文）

---

## 相关资源

- [产品需求文档](./docs/01-产品需求文档(PRD).md)
- [系统架构设计](./docs/02-系统架构设计.md)
- [部署运维方案](./docs/10-部署与运维方案.md)
- [CHANGELOG](../CHANGELOG.md)

---

> 📝 OfficeTool v2.0 由产品部、研发部、测试部联合交付。感谢所有贡献者的努力。
