# OfficeTool 2.0

中文 | [English](#officetool-20-english)

OfficeTool 是一个可私有化部署的企业文档智能解析与问答系统，面向文档入库、混合检索、智能问答、答案溯源和知识图谱可视化场景。

## 核心能力

- 多格式文档解析：支持 PDF、Word、PPT、Excel、TXT、Markdown、CSV、JSON、HTML、XML 等格式。
- 智能入库管道：上传后自动完成解析、分块、实体抽取、向量化和多库存储。
- 混合检索 RAG：融合 Milvus 向量检索、Elasticsearch BM25 关键词检索和 Neo4j 知识图谱检索。
- RRF 融合排序：统一融合多路召回结果，并支持向量、关键词、图谱任一路失败时容错降级。
- 智能问答：支持 SSE 流式输出、多轮对话记忆、答案溯源和相关度展示。
- 知识图谱：基于实体和关系构建图谱，前端使用 AntV G6 可视化。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18、TypeScript、Ant Design 5、Zustand、AntV G6 |
| 后端 | FastAPI、SQLAlchemy async、Pydantic、Celery |
| 数据层 | PostgreSQL、Redis、MinIO、Milvus、Elasticsearch、Neo4j |
| 模型层 | Sentence Transformers、LLM Provider、RAG Pipeline、KG Extractor |
| 部署 | Docker Compose、Nginx |

## 项目结构

```text
OfficeTool/
|-- app/
|   |-- api/              # FastAPI 路由
|   |-- core/             # 配置、数据库、安全、响应封装
|   |-- engine/           # parser、rag、kg、llm 核心引擎
|   |-- services/         # 业务编排服务
|   |-- tasks/            # Celery 异步任务
|   |-- models/           # SQLAlchemy 模型
|   |-- schemas/          # Pydantic Schema
|   |-- frontend/         # React 前端
|   |-- tests/            # 后端测试
|   |-- docker-compose.yml
|   `-- docker-compose.prod.yml
|-- docs/                 # 产品、架构、RAG、图谱、部署文档
|-- deploy/               # Nginx 与部署配置
|-- Agents.md             # 项目开发规范
`-- README.md
```

## 本地开发启动

### 1. 启动基础服务

```powershell
cd app
docker compose up -d postgres redis minio etcd milvus elasticsearch neo4j
```

### 2. 启动后端

```powershell
cd app
py -3.12 scripts\run_pg_backend.py
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

### 3. 启动 Celery Worker

```powershell
cd app
py -3.12 scripts\run_pg_celery.py
```

### 4. 启动前端

```powershell
cd app\frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5176
```

访问地址：`http://127.0.0.1:5176`

## Docker Compose 启动

开发环境全量启动：

```powershell
cd app
docker compose up -d --build
```

查看容器：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f backend
docker compose logs -f celery-worker
```

停止服务：

```powershell
docker compose down
```

生产环境启动：

```powershell
cd app
docker compose -f docker-compose.prod.yml up -d --build
```

## 重要端口

| 服务 | 地址 |
| --- | --- |
| 前端 | http://127.0.0.1:5176 |
| 后端 API | http://127.0.0.1:8000 |
| MinIO Console | http://127.0.0.1:9001 |
| Elasticsearch | http://127.0.0.1:9200 |
| Neo4j Browser | http://127.0.0.1:7474 |
| Milvus | 127.0.0.1:19530 |
| PostgreSQL | 127.0.0.1:5432 |
| Redis | 127.0.0.1:6379 |

## 验证命令

后端测试：

```powershell
cd app
py -3.12 -m pytest
```

前端构建：

```powershell
cd app\frontend
npm run build
```

## 文档

详细产品和技术文档见 `docs/`：

- `docs/01-产品需求文档(PRD).md`
- `docs/02-系统架构设计.md`
- `docs/06-文档解析引擎设计.md`
- `docs/07-RAG与检索系统设计.md`
- `docs/08-知识图谱与实体抽取设计.md`
- `docs/10-部署与运维方案.md`

## 开发规范

开发约定见 `Agents.md`。架构、RAG、解析、图谱、UI 或部署方案发生变化时，需要同步更新 `docs/` 中对应文档。

---

# OfficeTool 2.0 English

[中文](#officetool-20) | English

OfficeTool is a privately deployable enterprise document intelligence system for document ingestion, hybrid retrieval, question answering, source citation, and knowledge graph visualization.

## Highlights

- Multi-format parsing for PDF, Word, PPT, Excel, TXT, Markdown, CSV, JSON, HTML, XML, and more.
- Document ingestion pipeline: upload, parse, chunk, extract entities, embed, and store across multiple databases.
- Hybrid RAG retrieval with Milvus vector search, Elasticsearch BM25 keyword search, and Neo4j graph retrieval.
- RRF fusion ranking with fault-tolerant degradation when vector, keyword, or graph retrieval is unavailable.
- Intelligent QA with SSE streaming, multi-turn conversation memory, answer citations, and relevance display.
- Knowledge graph visualization in the frontend with AntV G6.

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript, Ant Design 5, Zustand, AntV G6 |
| Backend | FastAPI, SQLAlchemy async, Pydantic, Celery |
| Data | PostgreSQL, Redis, MinIO, Milvus, Elasticsearch, Neo4j |
| Model | Sentence Transformers, LLM providers, RAG pipeline, KG extractor |
| Deploy | Docker Compose, Nginx |

## Repository Layout

```text
OfficeTool/
|-- app/
|   |-- api/              # FastAPI routes
|   |-- core/             # config, database, security, response helpers
|   |-- engine/           # parser, rag, kg, llm engines
|   |-- services/         # business orchestration services
|   |-- tasks/            # Celery async tasks
|   |-- models/           # SQLAlchemy models
|   |-- schemas/          # Pydantic schemas
|   |-- frontend/         # React frontend
|   |-- tests/            # backend tests
|   |-- docker-compose.yml
|   `-- docker-compose.prod.yml
|-- docs/                 # product, architecture, RAG, graph, deployment docs
|-- deploy/               # Nginx and deployment config
|-- Agents.md             # project development guidelines
`-- README.md
```

## Local Development

### 1. Start infrastructure services

```powershell
cd app
docker compose up -d postgres redis minio etcd milvus elasticsearch neo4j
```

### 2. Start backend

```powershell
cd app
py -3.12 scripts\run_pg_backend.py
```

Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

### 3. Start Celery worker

```powershell
cd app
py -3.12 scripts\run_pg_celery.py
```

### 4. Start frontend

```powershell
cd app\frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5176
```

Open `http://127.0.0.1:5176`.

## Docker Compose

Start the development stack:

```powershell
cd app
docker compose up -d --build
```

Check containers:

```powershell
docker compose ps
```

View logs:

```powershell
docker compose logs -f backend
docker compose logs -f celery-worker
```

Stop services:

```powershell
docker compose down
```

Start the production stack:

```powershell
cd app
docker compose -f docker-compose.prod.yml up -d --build
```

## Ports

| Service | Address |
| --- | --- |
| Frontend | http://127.0.0.1:5176 |
| Backend API | http://127.0.0.1:8000 |
| MinIO Console | http://127.0.0.1:9001 |
| Elasticsearch | http://127.0.0.1:9200 |
| Neo4j Browser | http://127.0.0.1:7474 |
| Milvus | 127.0.0.1:19530 |
| PostgreSQL | 127.0.0.1:5432 |
| Redis | 127.0.0.1:6379 |

## Verification

Backend tests:

```powershell
cd app
py -3.12 -m pytest
```

Frontend build:

```powershell
cd app\frontend
npm run build
```

## Documentation

Detailed product and technical documentation lives in `docs/`:

- `docs/01-产品需求文档(PRD).md`
- `docs/02-系统架构设计.md`
- `docs/06-文档解析引擎设计.md`
- `docs/07-RAG与检索系统设计.md`
- `docs/08-知识图谱与实体抽取设计.md`
- `docs/10-部署与运维方案.md`

## Development Guidelines

See `Agents.md` for project development rules. When architecture, RAG, parsing, graph, UI, or deployment behavior changes, update the corresponding documentation under `docs/`.
