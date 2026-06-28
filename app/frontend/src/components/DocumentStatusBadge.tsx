import React from 'react';
import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import type { DocStatus } from '../api/document';

interface Props {
  status: DocStatus;
}

const statusConfig: Record<
  DocStatus,
  { color: string; icon: React.ReactNode; label: string }
> = {
  uploaded: { color: '#1677FF', icon: <UploadOutlined />, label: '已上传' },
  processing: { color: '#FAAD14', icon: <ClockCircleOutlined />, label: '解析中' },
  ready: { color: '#52C41A', icon: <CheckCircleOutlined />, label: '就绪' },
  error: { color: '#FF4D4F', icon: <CloseCircleOutlined />, label: '失败' },
};

const DocumentStatusBadge: React.FC<Props> = ({ status }) => {
  const config = statusConfig[status] || statusConfig.processing;
  return (
    <Tag color={config.color} icon={config.icon}>
      {config.label}
    </Tag>
  );
};

export default DocumentStatusBadge;
