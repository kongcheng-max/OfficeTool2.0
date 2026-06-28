# BUG-041: 文件夹上传时 .zip 文件上传失败

| 属性 | 值 |
|------|-----|
| 发现日期 | 2026-06-28 |
| 严重程度 | **中** / Medium |
| 影响范围 | 文件夹上传功能 |
| 责任部门 | 前端开发组 |
| 状态 | Open |

## 现象

使用「文件夹上传」选择一个包含 .zip 文件的文件夹后，其他格式文件上传成功，.zip 文件上传失败。

## 根因

`E:\OfficeTool\app\frontend\src\pages\Documents\index.tsx:235-248`：
```tsx
<input ref={folderInputRef} type="file" webkitdirectory directory
  onChange={(e) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      setBatchFiles(files);  // ← 所有文件（含 .zip）直接加入批量上传
      setBatchModalOpen(true);
    }
  }}
/>
```

文件夹内的所有文件（包括 .zip）都直接加入 `batchFiles`，然后通过 `handleBatchUpload` → `batchUploadDocuments` → `POST /documents/batch` 提交。

后端批量上传端点调用 `create_document()` → `ParserRegistry.find_for()`，没有注册 `.zip` 解析器 → `BadRequestError("不支持的文件格式")`。

正确的做法：.zip 文件应通过 `POST /documents/import-zip`（ZIP 导入）处理，而非普通文档上传。

## 修复方案

在 `onChange` 中过滤掉 .zip 文件，对 .zip 分别调用 `importZip` API：

```tsx
onChange={(e) => {
  const allFiles = Array.from(e.target.files || []);
  const zipFiles = allFiles.filter(f => f.name.toLowerCase().endsWith('.zip'));
  const otherFiles = allFiles.filter(f => !f.name.toLowerCase().endsWith('.zip'));
  // .zip 自动解压导入
  zipFiles.forEach(f => handleZipImport(f));
  // 其他文件走批量上传
  if (otherFiles.length > 0) {
    setBatchFiles(otherFiles);
    setBatchModalOpen(true);
  }
  e.target.value = '';
}}
```

## 影响

用户拖入包含 .zip 的文件夹时部分文件上传失败。
