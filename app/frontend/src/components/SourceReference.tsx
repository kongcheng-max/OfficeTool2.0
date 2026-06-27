import React from 'react';
import { Card, Typography } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import type { SourceInfo } from '../api/qa';

const { Text, Paragraph } = Typography;

interface Props {
  source: SourceInfo;
}

const SourceReference: React.FC<Props> = ({ source }) => {
  return (
    <Card
      size="small"
      style={{
        marginBottom: 6,
        background: '#fafafa',
        border: '1px solid #f0f0f0',
      }}
      bodyStyle={{ padding: '8px 12px' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <FileTextOutlined style={{ color: '#1677FF' }} />
        <Text strong style={{ fontSize: 13 }}>
          {source.document_name}
        </Text>
        {source.page != null && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            P{source.page}
          </Text>
        )}
      </div>
      <Paragraph
        ellipsis={{ rows: 2 }}
        type="secondary"
        style={{ fontSize: 12, margin: 0 }}
      >
        {source.chunk_text}
      </Paragraph>
    </Card>
  );
};

export default SourceReference;
