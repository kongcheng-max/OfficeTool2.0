# BUG-002: Milvus 镜像标签错误导致 docker compose up 失败

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | AC08 |
| **发现方式** | 部署测试 |
| **状态** | Fixed (已修复标签) |

## 现象
`docker compose up` 报错：
```
Error response from daemon: failed to resolve reference "docker.io/milvusdb/milvus:v2.3.4-latest": not found
```

## 根因
`app/docker-compose.yml` 中 milvus 服务的镜像标签为 `milvusdb/milvus:v2.3.4-latest`，该标签不存在于 Docker Hub。

## 修复
将标签改为 `milvusdb/milvus:v2.3.4`（已在本次测试中修复）。
