# BUG-032: 无法上传 .jpg / .png 图片文件

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **高** / High |
| 影响范围 | 图片上传功能完全不可用 |
| 责任部门 | 前端开发组 |
| 状态 | Open |

## 现象

拖拽 .jpg / .png 文件到上传区域，前端直接拒绝，提示「不支持的文件格式」。

## 根因

`E:\OfficeTool\app\frontend\src\components\DocumentUpload.tsx:8`：
```typescript
const ALLOWED_EXTS = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md',
                       '.text', '.markdown', '.mdown'];
```

`E:\OfficeTool\app\frontend\src\pages\Documents\index.tsx:291`：
```
accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md,.pptx,.ppt,.csv,.json,.html,.xml"
```

**两个上传组件都没有包含任何图片扩展名。**

后端 OCR 解析器已经存在并注册 (`E:\OfficeTool\app\engine\parser\ocr.py`)，注册了以下格式：
```python
[".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"]
```

所以瓶颈完全在前端文件过滤。

## 修复方案

1. `DocumentUpload.tsx` — `ALLOWED_EXTS` 追加：`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp`
2. `Documents/index.tsx` — `accept` 属性同样追加
3. 提示文案更新
4. 需确认后端 OCR 依赖（pytesseract / easyocr）是否已在 Dockerfile 中安装

## 影响

用户无法通过任何前端入口上传图片文件，即使后端完全具备 OCR 解析能力。
