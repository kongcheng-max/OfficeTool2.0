# CHANGELOG

## v2.0.0 (2026-07-11) — GA 生产就绪

### 🚀 新功能

#### 性能优化
- **PDF 流式解析**: 大文件分页批处理（每 20 页一批），支持页面范围参数，100MB+ 文件不再内存溢出
- **文档布局分析**: 多栏识别、页眉页脚过滤、表格定位，提升非结构化文档解析质量
- **Cross-encoder 语义精排**: 集成 bge-reranker-v2-m3，对 RRF 融合结果二次排序，Top-5 准确率显著提升
- **查询改写扩展召回**: LLM 自动生成查询变体 + BM25 互补检索，召回率提升
- **LLM 问答缓存**: Redis 缓存相同问题结果（TTL 1h），减少重复 LLM 调用
- **解析结果缓存**: MD5 去重 + Redis 缓存，相同文件跳过重解析
- **数据库复合索引**: 4 个复合索引优化文档列表、MD5 去重、标签查重等高频查询
- **Nginx 生产级配置**: gzip 压缩、静态资源浏览器缓存（1y immutable）、keepalive 连接池
- **文档状态细化**: 新增 `parsed` 状态（解析完成/Embedding 未完成），状态流转更精确

#### 安全加固
- **RBAC 角色权限**: admin / editor / viewer 三角色权限体系，含能力矩阵与路由装饰器
- **操作审计日志**: 全量记录用户操作（user/action/target/IP/time/result），仅 admin 可查
- **API 限流**: Token Bucket 算法，100 req/min/用户，超限返回 429 + Retry-After
- **AES-256 文档加密**: 可选开启的文档原文加密存储
- **管理后台**: 用户管理（角色修改/删除）+ 审计日志分页查询，仅 admin 可见
- **NL2Cypher 图谱问答**: 自然语言自动转 Cypher 查询，直接对话知识图谱

#### 部署与工程化
- **生产 Docker Compose**: 全量 10 服务编排（PG+Redis+MinIO+ES+Neo4j+Milvus+App+Nginx+Celery）
- **URL Token 认证**: 支持 `?token=` 参数传递 JWT，解决 iframe/图片/下载等浏览器原生请求的认证问题
- **轻量部署方案**: 单机 SQLite 模式一键部署脚本，无需 Docker

### 🔧 改进

- PDF 解析器全面重构（+242 行），支持流式输出
- RRF 融合去重改用 MD5 哈希 key，修复前 100 字符相同导致误合并 (BUG-064)
- 多轮对话 Prompt 结构优化，修复上下文串位问题 (BUG-068)
- 文档下载/预览 URL 认证修复 (BUG-051)
- 知识库删除时资源清理（Milvus/ES/文件）(BUG-044)
- 文档状态 error vs failed 前后端统一 (BUG-045)
- Alembic 迁移脚本 PG 兼容性修复 (BUG-054)
- 大文件上传内存保护 (BUG-055)

---

## v1.0.0-beta (2026-06-28) — Beta 高级功能

### 🚀 新功能

#### 文档解析扩展
- PPTX 解析器：幻灯片文字 + 表格 + 备注
- CSV/JSON 解析器：结构化数据平铺
- HTML/XML 解析器：标签剥离、纯文本提取
- 图片 OCR 解析器：PaddleOCR + Tesseract 双引擎

#### 全文检索与混合检索
- Elasticsearch 8.x + IK 中文分词器集成
- BM25 关键词检索
- 三路混合检索（向量 + BM25 + 图谱）→ RRF 融合

#### 知识图谱
- LLM 实体抽取：6 类实体（PERSON/ORG/DATE/MONEY/LOCATION/TERM）
- 规则引擎辅助：正则抽取日期、金额、身份证、手机号
- 关系抽取：共现分析 + LLM 语义推理，9 种关系类型
- Neo4j 5.x 图谱存储
- 图谱可视化：@antv/g6 交互式网络图

#### 对话增强
- 答案溯源：每条回答附带引用来源（文档名 + 原文 + 页码）
- 多轮对话：上下文记忆 + 代词消解，支持 5 轮追问
- 流式输出：SSE token 流

#### 知识库管理
- 批量上传 + ZIP 自动解压导入
- 标签系统完整 CRUD + 统计
- 文档版本追踪 + 历史版本查看
- 文档在线预览（PDF + DOCX 转 HTML）

---

## v0.1.0-mvp (2026-06-27) — MVP 核心链路

### 🚀 首次发布

- 用户注册/登录（bcrypt + JWT）
- 5 种格式文档解析（PDF/DOCX/XLSX/TXT/MD）
- RAG 管道：文本分块 → Embedding → Milvus 向量存储 → 检索
- LLM 问答：通义千问 / DeepSeek 双网关
- 知识库 CRUD
- Docker 开发环境
- React 前端（Vite + Ant Design）
