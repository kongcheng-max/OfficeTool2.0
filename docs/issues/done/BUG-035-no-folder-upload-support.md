# BUG-035: 不支持整个文件夹上传

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **中** / Medium |
| 影响范围 | 批量上传体验 |
| 责任部门 | 前端开发组 |
| 状态 | Open |

## 现象

无法选中整个文件夹拖入上传区域。只能逐个选择文件或拖入多个文件。

## 根因

`E:\OfficeTool\app\frontend\src\components\DocumentUpload.tsx:62-67` 和 `E:\OfficeTool\app\frontend\src\pages\Documents\index.tsx` 中的 `Dragger` 组件没有设置 HTML5 目录选择属性：

缺少：
```html
<!-- HTML input 原生属性 -->
<input type="file" webkitdirectory directory />
```

Ant Design `Upload` 组件不直接支持 `webkitdirectory`，需要通过自定义方式实现。

## 修复方案

1. 在批量上传 Tab 增加文件夹上传入口：
   - 使用隐藏的 `<input type="file" webkitdirectory />` 触发文件夹选择
   - 或在 `Dragger` 的 `beforeUpload` 中处理 `File.webkitRelativePath` 属性
2. 保留目录结构信息（`webkitRelativePath`）作为文档的元数据标签

## 影响

用户有大量文档时（如法律合同库、财务报告库），需要逐个文件选择，体验差。
