import React from 'react';
import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
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
  uploaded: { color: '#3370FF', icon: <UploadOutlined />, label: '已上传' },
  processing: { color: '#E67E00', icon: <ClockCircleOutlined />, label: '解析中' },
  parsed: { color: '#C77700', icon: <SyncOutlined spin />, label: '索引中' },
  ready: { color: '#21A366', icon: <CheckCircleOutlined />, label: '就绪' },
  failed: { color: '#F54A45', icon: <CloseCircleOutlined />, label: '失败' },
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
