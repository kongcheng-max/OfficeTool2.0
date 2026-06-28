# BUG-040: 批量分配标签按钮无法点击

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **高** / High |
| 影响范围 | 文档批量标签分配 |
| 责任部门 | 前端开发组 |
| 状态 | Open |

## 现象

创建了标签，但点击「批量分配标签」按钮时无响应 / 按钮灰色不可点击。

## 根因

`E:\OfficeTool\app\frontend\src\pages\Documents\index.tsx:255-262`：
```tsx
<Button
  icon={<TagOutlined />}
  disabled={selectedRowKeys.length === 0}
  onClick={() => setTagModalOpen(true)}
>
  批量分配标签
  {selectedRowKeys.length > 0 ? ` (${selectedRowKeys.length})` : ''}
</Button>
```

按钮在 `selectedRowKeys.length === 0` 时被 `disabled`。

表格虽然配置了 `rowSelection`（第 296 行），但用户可能没有注意到需要**先勾选文档行**的多选框才能启用按钮。按钮在没有选中任何行时没有提示说明原因。

## 修复方案

1. 在按钮旁增加提示文字："请先勾选文档"
2. 当 disabled 时改用 `tooltip` 说明原因
3. 或者在没有任何选择时按钮仍然可点击但弹窗显示提示

## 影响

用户不知道需要先勾选行才能批量分配标签。
