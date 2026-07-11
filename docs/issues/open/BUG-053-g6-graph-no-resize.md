# BUG-053: 知识图谱画布不响应窗口缩放

| 属性 | 值 |
|------|---|
| **严重级别** | 🟢 Low |
| **影响模块** | 前端知识图谱可视化 |
| **发现方式** | 代码审查 |
| **状态** | Open |
| **发现日期** | 2026-07-06 |

## 现象

知识图谱页面（`pages/Graph/index.tsx`）使用 `@antv/g6` 渲染关系网络图，但画布尺寸在初始化时根据 `containerRef.current.clientWidth/clientHeight` 固定计算，之后不再更新。当用户缩放浏览器窗口或侧边栏折叠时，图谱画布尺寸不随之调整，导致内容被截断或留有大量空白。

## 根因

`pages/Graph/index.tsx:105-106`:
```tsx
const width = containerRef.current?.clientWidth || 800;
const height = containerRef.current?.clientHeight || 500;
```

这些值只在图表创建时（`renderGraph` 被调用时）读取一次。没有 `ResizeObserver` 或 `window.resize` 事件监听器来检测容器尺寸变化并更新图表。

`renderGraph` 函数每次被调用时会销毁旧的 G6 实例并创建新的（通过 `g6.destroy()` 和重新 `new G6.Graph(...)`），这本身就很重，且只在用户点击实体或搜索时触发——不响应窗口变化。

## 复现步骤

1. 进入知识图谱页面
2. 手动缩放浏览器窗口
3. 观察图谱画布 → 尺寸不变，可能溢出或留白

## 影响

- 🟢 窗口缩放后图谱显示不完整或布局异常
- 🟢 在大屏/小屏切换时视觉体验差

## 修复建议

使用 `ResizeObserver` 监听容器尺寸变化，触发图表 resize：

```tsx
useEffect(() => {
  const container = containerRef.current;
  if (!container) return;

  const observer = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      if (g6.current) {
        g6.current.changeSize(width, height);
      }
    }
  });

  observer.observe(container);
  return () => observer.disconnect();
}, []);
```

注意：`g6.changeSize(width, height)` 比销毁重建更高效，应替代当前的 `g6.destroy()` + 重建模式。
