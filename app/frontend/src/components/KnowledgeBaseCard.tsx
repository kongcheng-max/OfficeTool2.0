import React from 'react';
import { Card, Tag, Space, Typography } from 'antd';
import { BookOutlined, FileTextOutlined, MessageOutlined } from '@ant-design/icons';

const { Text } = Typography;

export interface KnowledgeBaseCardProps {
  id: string;
  name: string;
  description?: string;
  documentCount: number;
  qaCount?: number;
  chunkCount?: number;
  tags?: string[];
  createdAt: string;
  onEnter: (id: string) => void;
  onManage: (id: string) => void;
}

const KnowledgeBaseCard: React.FC<KnowledgeBaseCardProps> = ({
  id,
  name,
  description,
  documentCount,
  qaCount,
  tags,
  createdAt,
  onEnter,
  onManage,
}) => {
  return (
    <Card
      hoverable
      style={{ height: '100%' }}
      actions={[
        <span key="enter" onClick={() => onEnter(id)}>
          进入
        </span>,
        <span key="docs" onClick={() => onManage(id)}>
          文档管理
        </span>,
      ]}
    >
      <Card.Meta
        avatar={<BookOutlined style={{ fontSize: 28, color: '#1677FF' }} />}
        title={
          <Space>
            <span>{name}</span>
          </Space>
        }
        description={
          <div>
            {description && (
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                {description}
              </Text>
            )}
            <Space size={16} style={{ marginBottom: 8 }}>
              <Text type="secondary">
                <FileTextOutlined /> {documentCount} 份文档
              </Text>
              <Text type="secondary">
                <MessageOutlined /> {qaCount} 次问答
              </Text>
            </Space>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              创建于 {new Date(createdAt).toLocaleDateString('zh-CN')}
            </Text>
            {tags && tags.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {tags.map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </div>
            )}
          </div>
        }
      />
    </Card>
  );
};

export default KnowledgeBaseCard;
