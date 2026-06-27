# BUG-011: 前端错误处理吞没异常信息

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响 AC** | AC06, AC07 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
多数前端页面使用 `catch {}` 或 `catch { // handled }` 空块吞没异常：

- `Login.tsx:25`: `} catch { // error handled by axios interceptor }`
- `Documents/index.tsx:61`: `} catch { // handled }`
- `Documents/index.tsx:79`: `} catch { // handled }`

## 根因
依赖 axios 拦截器的 `message.error()` 处理。但拦截器在 `response.data.code !== 0` 时调用 `message.error(msg)` 然后 `reject`。部分情况下（网络断开、超时等），可能双次弹出错误（拦截器一次，页面可能再次），或登录页重定向循环。

## 影响
- 操作失败时可能无用户提示
- 错误恢复路径不明确

## 修复建议
统一错误处理策略，避免混合使用拦截器 + 页面 catch 的双层处理。
