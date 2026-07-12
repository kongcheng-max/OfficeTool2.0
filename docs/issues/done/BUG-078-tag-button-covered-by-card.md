# BUG-078: 知识库管理页面「标签管理」按钮被下方卡片遮挡

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | 前端 → 知识库管理页面 |
| **发现方式** | 用户手动测试 |
| **状态** | 🔴 待修复 |
| **发现日期** | 2026-07-11 |

---

## 现象

知识库管理界面，卡片下方的「标签管理」按钮被下一行的知识库卡片遮挡，无法点击。

## 根因

`KnowledgeBase/index.tsx:161-188` 中「标签管理」按钮放在 `Card` 组件外、`Col` 内的独立 `<div>` 中：

```tsx
<Row gutter={[16, 16]}>
  {list.map((kb) => (
    <Col xs={24} sm={12} lg={8} key={kb.id}>
      <KnowledgeBaseCard ... />      {/* 卡片 */}
      <div style={{ marginTop: 8 }}>  {/* 按钮在 Card 外面 */}
        <Button>标签管理</Button>
      </div>
    </Col>
  ))}
</Row>
```

`Row` 的 `gutter` 仅控制 `Col` 之间的水平/垂直间距（16px），但 `Col` 内高度不统一时，下一行卡片会紧贴上一行最短 `Col` 的底部。8px 的 `marginTop` 不足以防止遮挡。

## 修复建议

方案 A：将标签按钮移入 `KnowledgeBaseCard` 的 `actions` 属性中：

```tsx
actions={[
  <span key="enter">进入</span>,
  <span key="docs">文档管理</span>,
  <span key="graph">知识图谱</span>,
  <span key="tags" onClick={() => onTagManage(id)}>标签管理</span>,
  ...
]}
```

方案 B：为按钮 wrapper 添加足够的 `marginBottom` 和 `position: relative; z-index: 1`：

```tsx
<div style={{ marginTop: 8, marginBottom: 16, textAlign: 'center' }}>
```
