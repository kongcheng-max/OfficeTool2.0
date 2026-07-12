# BUG-052: 知识库删除按钮未接入 UI，用户无法删除知识库

| 属性 | 值 |
|------|---|
| **严重级别** | 🟡 Medium |
| **影响模块** | 前端知识库管理 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

在前端知识库管理页面（`pages/KnowledgeBase/index.tsx`）中，`handleDelete` 函数已实现（第 75-83 行），但该函数**未在任何 UI 元素中被调用**。`KnowledgeBaseCard` 组件没有删除按钮或操作项。用户无法通过前端界面删除知识库。

## 根因

`pages/KnowledgeBase/index.tsx:75-83`:
```tsx
const handleDelete = async (kbId: string) => {
  try {
    await deleteKB(kbId);
    message.success('知识库已删除');
    fetchList();
  } catch (e: any) {
    console.debug('[BUG-011] handleDeleteKB failed:', e?.message || e);
  }
};
```

此函数定义完整，API 也已实现（`api/kb.ts` 导出了 `deleteKB`），后端端点 `DELETE /api/v1/knowledge-bases/{kb_id}` 也正常工作。但 `KnowledgeBaseCard` 组件（`components/KnowledgeBaseCard.tsx`）没有接收 `onDelete` 回调 prop，也没有渲染删除按钮。

`KnowledgeBaseCard` 当前暴露的 actions 只有：
- 进入知识库（chat 页面）
- 文档管理
- 知识图谱

## 影响

- 🟡 用户无法删除不需要的知识库，只能通过 API 工具手动调用
- 🟡 测试数据和管理员清理知识库需要绕过前端

## 修复建议

1. 为 `KnowledgeBaseCard` 组件添加 `onDelete` prop
2. 在卡片上添加删除按钮（使用 `Popconfirm` 确认对话框，防止误删）
3. 在 `KnowledgeBase/index.tsx` 中将 `handleDelete` 传递给 `KnowledgeBaseCard`

```tsx
// KnowledgeBaseCard.tsx
interface Props {
  // existing props...
  onDelete?: (id: string) => void;
}

// 在卡片 actions 中添加：
<Popconfirm
  title="确定删除此知识库？所有文档将被删除且不可恢复"
  onConfirm={() => onDelete?.(kb.id)}
>
  <Button type="text" danger icon={<DeleteOutlined />}>
    删除
  </Button>
</Popconfirm>
```

> **关联 Bug**: BUG-044（知识库删除不清理外部资源），应同步修复。
