# OfficeTool 2.0

OfficeTool is a privately deployable enterprise document intelligence system for document parsing, hybrid retrieval, question answering, source citation, and knowledge graph visualization.

## Highlights

- Multi-format parsing for PDF, Word, PPT, Excel, TXT, Markdown, CSV, JSON, HTML, XML and more.
- Document ingestion pipeline: upload, parse, chunk, extract entities, embed, and store across multiple databases.
- Hybrid RAG retrieval with Milvus vector search, Elasticsearch BM25, and Neo4j graph retrieval.
- RRF fusion ranking with fault-tolerant degradation when vector, keyword, or graph retrieval is unavailable.
- SSE streaming QA, multi-turn conversation memory, answer source references, and relevance display.
- Knowledge graph visualization in the frontend using AntV G6.

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
├── app/
│   ├── api/              # FastAPI routes
│   ├── core/             # config, database, security, response helpers
│   ├── engine/           # parser, rag, kg, llm engines
│   ├── services/         # business orchestration services
│   ├── tasks/            # Celery async tasks
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── frontend/         # React frontend
│   ├── tests/            # backend tests
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── docs/                 # product, architecture, RAG, graph, deployment docs
├── deploy/               # Nginx and deployment config
├── Agents.md             # project development guidelines
└── README.md
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

Backend health check:

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
