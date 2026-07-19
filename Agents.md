# Agents.md

## 项目定位
OfficeTool 是私有化部署的企业文档智能解析与问答系统，技术栈为 FastAPI + React 18 + PostgreSQL + Milvus + Neo4j + Elasticsearch + Redis + Docker。

## 架构边界
- 前端：`app/frontend/`，使用 React 18、TypeScript、Ant Design 5、Zustand、AntV G6。
- 后端：`app/api/`、`app/services/`、`app/core/`，使用 FastAPI、SQLAlchemy async、Pydantic。
- 数据层：PostgreSQL 存元数据，MinIO/本地 FS 存原文件，Redis 存缓存/会话/Celery 队列，Milvus 存向量，Elasticsearch 存 BM25 索引，Neo4j 存图谱。
- 模型层：`app/engine/`，包含 parser、rag、kg、llm；模型、存储、LLM 提供商必须通过抽象或配置切换。

## 开发约定
- 保持单向依赖：API -> service -> engine/data；不要让前端或路由直接操作数据库、Milvus、Neo4j、ES。
- 文档入库链路必须保持：上传 -> 解析 -> 分块 -> 实体抽取 -> 向量化 -> 多库存储；长任务走 Celery。
- RAG 检索必须保留容错降级：Milvus 向量检索、ES BM25、Neo4j 图谱检索任一路失败时，其他结果仍可返回，并用 RRF 融合排序。
- 问答接口优先支持 SSE 流式输出、多轮会话、答案来源和置信度；不要返回无来源的编造答案。
- 新增文档格式时，实现 `BaseParser` 并注册到 `ParserRegistry`，输出统一 `Chunk`/metadata。
- 前端复用 Ant Design 组件和现有主题；知识图谱使用 AntV G6；接口访问统一放在 `app/frontend/src/api/`。
- 配置和密钥只走环境变量或配置文件；不要硬编码 API Key、密码、模型路径和服务地址。
- 数据库结构变更必须新增 Alembic migration；删除 KB/文档时同步清理 PG、MinIO、Milvus、ES、Neo4j 相关数据。

## Docker 与服务
- Compose 文件以 `app/docker-compose.yml` 和 `app/docker-compose.prod.yml` 为准；不要随意改服务名、端口和 volume。
- 核心服务包括 backend、celery-worker、nginx、postgres、redis、minio、milvus、elasticsearch、neo4j；Milvus 相关依赖按当前 compose 保持。
- 生产环境必须启用健康检查、资源限制、非默认密码、审计日志和限流。

## 验证命令
- 后端测试：在 `app/` 下运行 `python -m pytest`。
- 前端构建：在 `app/frontend/` 下运行 `npm run build`。
- 部署检查：启动 compose 后访问 `/api/v1/health` 或 `/api/health`，以当前路由实现为准。

## 文档同步
架构、RAG、解析、图谱、UI 或部署方案发生变化时，同步更新 `docs/` 中对应文档，避免代码与设计说明脱节。
