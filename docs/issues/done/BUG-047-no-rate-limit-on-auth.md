# BUG-047: 认证端点缺少速率限制，存在暴力破解风险

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | 安全性 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

`POST /api/v1/auth/login` 和 `POST /api/v1/auth/register` 端点没有任何速率限制（rate limiting），攻击者可以无限次尝试用户名/密码组合。

## 根因

1. `api/auth.py` 中两个端点均为普通 FastAPI endpoint，未加任何限流装饰器或中间件
2. `core/config.py` 中未定义任何速率限制相关配置
3. 项目未集成速率限制库（如 `slowapi`、`fastapi-limiter`）

## 影响

- 🟡 **暴力破解**: 攻击者可对已知用户名进行无限次密码尝试
- 🟡 **账号枚举**: 注册端点的"用户名已存在"错误可用于枚举有效用户名
- 🟡 **资源消耗**: 大量并发登录请求可能耗尽数据库连接池

## 修复建议

1. **添加速率限制中间件**：
   - 登录端点：每 IP 每分钟最多 5 次失败尝试，超过后锁定 15 分钟
   - 注册端点：每 IP 每小时最多 3 次注册
   
2. **账号锁定机制**：
   - 连续 5 次登录失败后暂时锁定账号 15 分钟
   - 在 `User` 模型中添加 `login_attempts` 和 `locked_until` 字段

3. **统一错误消息**（注册端点）：
   - `auth.py:23` 的 "用户名已存在" 和 `auth.py:29` 的 "邮箱已被注册" 可被用于枚举用户
   - 建议改为通用消息或添加验证码机制

4. **推荐使用 slowapi**：
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   
   @router.post("/login")
   @limiter.limit("5/minute")
   async def login(...): ...
   ```
