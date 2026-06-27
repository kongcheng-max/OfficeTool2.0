import React from 'react';
import { Upload, message, App } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { uploadDocument } from '../api/document';

const { Dragger } = Upload;

interface Props {
  kbId: string;
  onSuccess: () => void;
  onClose: () => void;
}

const DocumentUpload: React.FC<Props> = ({ kbId, onSuccess, onClose }) => {
  const { message: msg } = App.useApp();

  const handleUpload = async (options: { file: File; onProgress?: (pct: number) => void; onSuccess: () => void; onError: (err: Error) => void }) => {
    const { file, onProgress, onSuccess: upSuccess, onError: upError } = options;
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
      accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md"
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
        支持 PDF, DOCX, XLSX, TXT, MD — 单文件最大 200MB
      </p>
    </Dragger>
  );
};

export default DocumentUpload;
