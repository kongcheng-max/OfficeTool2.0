# BUG-008: 安全配置使用硬编码默认值

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | AC06 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/core/config.py` 中存在多处硬编码的安全敏感默认值：

```python
SECRET_KEY: str = "change-me-in-production-use-a-real-secret"
MINIO_ACCESS_KEY: str = "minioadmin"
MINIO_SECRET_KEY: str = "minioadmin"
```

## 根因
MVP 阶段使用默认配置方便开发。

## 影响
- JWT 令牌可被伪造（SECRET_KEY 暴露）
- MinIO 可被未授权访问
- CORS 设置为 `allow_origins=["*"]` 允许任意跨域请求

## 修复建议
1. 移除所有硬编码 secret，要求通过环境变量提供
2. 启动时检查关键安全配置是否已修改
3. 生产环境 CORS 限制为白名单域名
