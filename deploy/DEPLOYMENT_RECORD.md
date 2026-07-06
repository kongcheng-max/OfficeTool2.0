# OfficeTool 轻量化部署 — 工作记录

> **日期**: 2026-07-06
> **环境**: 阿里云 ECS 2C2G + 宝塔 Linux + 域名 officetool2.xyz
> **目标**: 面试展示用途，轻量化部署（无 Docker，SQLite 本地存储）

---

## 一、项目背景

OfficeTool 是企业智能知识库平台，技术栈为 FastAPI（Python）+ React（TypeScript）+ Ant Design。完整版依赖 7 个基础服务（PostgreSQL、Redis、MinIO、etcd、Milvus、Elasticsearch、Neo4j），最低要求 8C16G。

本次在 2C2G 阿里云 ECS 上完成轻量化部署，用于面试作品展示。

---

## 二、架构变更

### 完整版 → 轻量化版

| 组件 | 完整版 | 轻量化版 | 说明 |
|------|--------|----------|------|
| 数据库 | PostgreSQL | **SQLite** | 代码已预设 USE_SQLITE 开关 |
| 缓存/队列 | Redis | 移除 | Celery 异步任务改为同步执行 |
| 对象存储 | MinIO | **本地文件系统** | 自动降级，无需配置 |
| 向量检索 | Milvus | 移除 | API 调用自动降级为空列表 |
| 全文搜索 | Elasticsearch | 移除 | 改用 SQL LIKE 查询 |
| 知识图谱 | Neo4j | 移除 | API 调用自动降级 |
| SSL | — | **certbot + Let's Encrypt** | 免费 HTTPS 证书 |

### 部署拓扑

```
用户浏览器 (https://officetool2.xyz)
  │
  ▼
Nginx (:443 → :80)
  ├── /api/* → FastAPI (:8000) ─── SQLite + 本地文件存储 + LLM API
  └── /*     → React 静态文件 (dist/)
```

---

## 三、代码改动

共修改 **3 个业务文件**，新增 **4 个部署配置**，提交 3 次：

| 文件 | 改动内容 |
|------|---------|
| `app/services/storage.py` | MinIO 可用性自动检测，无凭证时降级为本地文件存储 |
| `app/services/document_service.py` | Celery 不可用时自动切换同步文档解析 |
| `app/services/qa_service.py` | Embedding 模型懒加载，加速应用启动 |
| `deploy/.env.lightweight` | 轻量化环境变量模板 |
| `deploy/nginx.conf` | Nginx 反向代理 + SPA 路由配置 |
| `deploy/officetool.service` | systemd 守护进程配置 |
| `deploy/deploy.sh` | 一键部署脚本（自动装 Python 3.11 / Node.js 18 / 依赖 / 构建前端 / 配 Nginx / 启动服务） |

---

## 四、当前可用功能

| 功能 | 状态 | 备注 |
|------|------|------|
| 用户注册/登录 | ✅ | JWT 认证 |
| 知识库 CRUD | ✅ | 创建、删除、列表 |
| 文档上传/解析 | ✅ | 支持 PDF/DOCX/XLSX/PPTX/TXT/MD/CSV/JSON/HTML/XML |
| 标签管理 | ✅ | 打标签、按标签筛选 |
| LLM 问答 | ⚠️ | LLM 通路正常，但无文档检索上下文 |
| 全文搜索 | ⚠️ | 仅 SQL LIKE 模糊查询 |
| 向量语义检索 | ❌ | 需 Milvus（内存不足） |
| 知识图谱 | ❌ | 需 Neo4j（内存不足） |
| 多轮对话历史 | ❌ | 需 Redis（内存不足） |

---

## 五、部署信息

| 项目 | 值 |
|------|-----|
| 服务器 | 阿里云 ECS 2C2G |
| 公网 IP | 8.217.117.36 |
| 域名 | officetool2.xyz |
| 项目路径 | /www/wwwroot/officetool/app |
| 虚拟环境 | /www/wwwroot/officetool/app/.venv |
| 前端文件 | /www/wwwroot/officetool/app/frontend/dist |
| 数据库 | SQLite（/www/wwwroot/officetool/app/officetool_dev.db） |
| 日志 | journalctl -u officetool |

### 日常维护命令

```bash
systemctl status officetool        # 查看后端状态
systemctl restart officetool       # 重启后端
systemctl stop officetool          # 停止后端
journalctl -u officetool -f        # 实时日志
nginx -t && nginx -s reload        # 重载 Nginx
cd /www/wwwroot/officetool/app && source .venv/bin/activate  # 进入虚拟环境
```

### 修改 .env 后生效

```bash
vim /www/wwwroot/officetool/app/.env
systemctl restart officetool
```

---

## 六、后续升级建议

| 优先级 | 事项 | 预计成本 |
|--------|------|---------|
| P0 | 申请 SSL 证书（certbot --nginx -d officetool2.xyz） | 免费 |
| P1 | 升级到 4C8G，安装 Redis + Milvus，恢复向量检索 | ¥200-300/月 |
| P2 | 升级到 8C16G，恢复 ES + Neo4j，功能全量上线 | ¥500-800/月 |
| P3 | 配置 CI/CD（Git push → 自动部署） | — |

---

## 七、踩坑记录

| 问题 | 原因 | 解决 |
|------|------|------|
| pip 安装卡住 | sentence-transformers 依赖 PyTorch 几百 MB | 耐心等待 10-15 分钟 |
| 启动报 CORS_ORIGINS 解析错误 | pydantic 要求 JSON 数组格式 | 改为 `["url1","url2"]` 格式 |
| 启动报 pymilvus 模块缺失 | 精简依赖时漏装 | `pip install pymilvus elasticsearch neo4j` |
| 端口 8000 被占用 | 前一次启动的残留进程 | `kill` 后重启 |
| certbot 报域名 NXDOMAIN | nslookup 确认 officetool.xyz vs officetool2.xyz | 使用正确域名 officetool2.xyz |
