# BUG-021: Dockerfile 缺少 Phase 2 所有 Python 依赖

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | 全部 Phase 2 AC |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
Dockerfile 第 12-32 行的 pip fallback 安装列表仅包含 Phase 1 依赖，缺少 Phase 2 新增的 7 个关键包。`docker compose up --build` 构建的镜像中：
- `from pptx import Presentation` → ImportError
- `from bs4 import BeautifulSoup` → ImportError
- `from elasticsearch import AsyncElasticsearch` → ImportError
- `from neo4j import GraphDatabase` → ImportError
- `from sentence_transformers import SentenceTransformer` → ImportError

## 缺失依赖
```
python-pptx>=0.6.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
elasticsearch[async]>=8.12.0
neo4j>=5.18.0
redis[hiredis]>=5.0.0
sentence-transformers>=2.7.0
```

## 修复
在 Dockerfile 的 pip install fallback 列表中添加以上 7 个包。
