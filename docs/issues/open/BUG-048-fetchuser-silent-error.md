# BUG-048: authStore.fetchUser 静默吞没错误，用户无感知 Token 过期

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | 前端认证状态管理 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

当 `authStore.fetchUser()` 调用失败时（如 Token 过期），错误被完全吞没，用户无任何提示。用户会突然在下次操作时被 401 重定向到 `/login` 页面，没有机会保存当前工作。

## 根因

`stores/authStore.ts:53-60`:

```typescript
fetchUser: async () => {
  try {
    const user = await getMe();
    localStorage.setItem('user', JSON.stringify(user));
    set({ user });
  } catch {
    // token expired — stay on current page, let interceptor handle redirect on next API call
  }
},
```

空 `catch` 块不记录日志、不通知用户、不更新状态。注释说明意图是让 axios 拦截器处理 401，但这造成以下问题：

1. `fetchUser` 在 AppLayout 挂载时调用（通过 `useEffect`），失败后用户看到的是过期的用户信息
2. 用户的下一步操作（如发送消息、上传文档）会触发 401 拦截器，突然跳转到登录页
3. 如果 Token 刚过期但用户正在填写表单，表单数据会丢失

## 影响

- 🟢 **用户体验差**: 静默的 Token 过期 + 突然的页面跳转
- 🟢 **数据丢失风险**: 用户在不知情的情况下可能丢失未保存的数据

## 修复建议

1. 在 `catch` 块中至少记录日志：`console.warn('Token expired or user fetch failed')`
2. 考虑在 `catch` 中主动清除 token 并设置 `user: null`，让 UI 能反映真实的认证状态
3. 在跳转登录页前给用户一个提示（全局 message/notification）
4. 考虑在 axios 拦截器中增加 token 刷新逻辑（如果有 refresh token 机制）

```typescript
fetchUser: async () => {
  try {
    const user = await getMe();
    localStorage.setItem('user', JSON.stringify(user));
    set({ user });
  } catch (e) {
    console.warn('获取用户信息失败，Token 可能已过期:', e);
    // 主动登出以保持 UI 状态一致
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ user: null, token: null });
  }
},
```
