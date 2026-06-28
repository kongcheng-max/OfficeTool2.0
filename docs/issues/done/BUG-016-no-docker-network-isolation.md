# BUG-016: Docker Compose 缺少网络隔离配置

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响 AC** | AC08 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/docker-compose.yml` 未定义自定义网络。所有服务位于默认 bridge 网络，服务间通过容器名通信，但无显式网络隔离。

## 根因
compose 文件缺少 `networks:` 顶层配置及服务级 `networks:` 声明。

## 影响
- 默认网络中的端口暴露策略不明确
- 无前后端子网隔离

## 修复建议
```yaml
networks:
  officetool-net:
    driver: bridge
```
每个服务添加 `networks: [officetool-net]`。
