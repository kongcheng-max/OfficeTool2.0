# BUG-012: DocumentUpload 无客户端文件大小校验

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响 AC** | AC01 |
| **发现方式** | 代码审查 |
| **状态** | Open |

## 现象
`app/frontend/src/components/DocumentUpload.tsx` 显示"单文件最大 200MB"，但未在客户端做文件大小判断。用户选择超大文件后，文件上传到后端才被拒绝。

## 根因
`handleUpload` 函数直接将文件传给 `uploadDocument`，无 `file.size > MAX_SIZE` 检查。

## 影响
- 用户体验差：大文件上传到后端才失败
- 浪费带宽和服务器资源

## 修复建议
在 `handleUpload` 开头添加：
```typescript
const MAX_SIZE = 200 * 1024 * 1024;
if (file.size > MAX_SIZE) {
  msg.error(`文件 ${file.name} 超过 200MB 限制`);
  upError(new Error('文件过大'));
  return;
}
```
