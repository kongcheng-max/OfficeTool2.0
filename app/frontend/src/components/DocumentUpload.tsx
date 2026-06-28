import React from 'react';
import { Upload, App } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { uploadDocument } from '../api/document';

const { Dragger } = Upload;

const ALLOWED_EXTS = [
  '.pdf', '.docx', '.doc', '.xlsx', '.xls',
  '.pptx', '.ppt', '.csv', '.json', '.html', '.xml',
  '.txt', '.md', '.text', '.markdown', '.mdown',
  '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp',
];

interface Props {
  kbId: string;
  onSuccess: () => void;
  onClose: () => void;
}

const DocumentUpload: React.FC<Props> = ({ kbId, onSuccess, onClose }) => {
  const { message: msg } = App.useApp();

  /** 上传前置校验：限制文件格式 + 大小 */
  const beforeUpload = (file: File): boolean | Promise<void> => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      msg.error(`不支持的文件格式: ${file.name}。支持: PDF, DOCX, XLSX, PPTX, CSV, JSON, HTML, XML, TXT, MD, JPG, PNG`);
      return false; // Ant Design 的 Upload 会阻止添加
    }
    const MAX = 200 * 1024 * 1024;
    if (file.size > MAX) {
      msg.error(`文件 ${file.name} 超过 200MB 限制`);
      return false;
    }
    return true;
  };

  const handleUpload = async (options: { file: File; onProgress?: (pct: number) => void; onSuccess: () => void; onError: (err: Error) => void }) => {
    const { file, onProgress, onSuccess: upSuccess, onError: upError } = options;

    // 双重校验（Ant Design customRequest 可能仍会传入未过滤的文件）
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      upError(new Error(`不支持的文件格式: ${file.name}`));
      return;
    }
    const MAX_SIZE = 200 * 1024 * 1024; // 200MB like BE setting
    if (file.size > MAX_SIZE) {
      msg.error(`${file.name} 超过 200MB 限制 (${(file.size / 1024 / 1024).toFixed(1)}MB)`);
      upError(new Error('文件过大'));
      return;
    }

    try {
      await uploadDocument(kbId, file, onProgress);
      msg.success(`${file.name} 上传成功`);
      upSuccess();
      onSuccess();
      onClose();
    } catch (e: any) {
      upError(e);
    }
  };

  return (
    <Dragger
      name="file"
      multiple
      customRequest={handleUpload as any}
      accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.csv,.json,.html,.xml,.txt,.md,.text,.markdown,.mdown,.jpg,.jpeg,.png,.bmp,.tiff,.tif,.webp"
      beforeUpload={beforeUpload as any}
      showUploadList={{
        showPreviewIcon: false,
        showRemoveIcon: true,
      }}
    >
      <p className="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
      <p className="ant-upload-hint">
        支持 PDF, DOCX, XLSX, PPTX, CSV, JSON, HTML, XML, TXT, MD, JPG, PNG — 单文件最大 200MB
      </p>
    </Dragger>
  );
};

export default DocumentUpload;
