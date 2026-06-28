# BUG-019: Vite 代理端口配置错误导致前端所有 API 请求 500

| 属性 | 值 |
|------|---|
| **严重级别** | 🔴 Critical |
| **影响 AC** | AC01, AC05, AC06, AC07 |
| **发现方式** | 人工手动测试 |
| **发现人** | 产品/用户 |
| **状态** | Fixed |

## 现象
前端所有页面（首页 Dashboard、知识库管理、文档管理、对话）点击后均提示：
```
Request failed with status code 500
```
无法创建知识库、无法上传文档、无法进行问答。

## 根因
`app/frontend/vite.config.ts:10` 中 Vite 开发服务器代理配置指向了错误端口：

```typescript
// ❌ 错误
proxy: {
  '/api': {
    target: 'http://localhost:8001',
  },
},
```

Docker Compose 中 backend 服务映射的是 **8000** 端口：
```yaml
backend:
  ports:
    - "8000:8000"
```

前端将 `/api` 请求代理到不存在的 `8001` 端口，Vite 返回 SPA fallback HTML 页面（HTTP 200），axios 解析 HTML 失败后抛错 "Request failed with status code 500"。

## 修复
```typescript
// ✅ 正确
target: 'http://localhost:8000',
```

## 经验教训
1. Q&A 阶段的 curl + Python 直接测试绕过了 Vite 代理，未覆盖前端→后端的完整链路
2. 应该增加端到端的浏览器/前端代理层测试
3. Docker 端口和 Vite 代理端口应有统一的配置来源或启动时校验
