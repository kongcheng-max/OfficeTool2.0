import React from 'react';
import { Card, Tag, Space, Typography } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import type { SourceInfo } from '../api/qa';

const { Text, Paragraph } = Typography;

const SOURCE_COLORS: Record<string, string> = {
  vector: '#1677FF',
  bm25: '#52C41A',
  kg: '#FAAD14',
};

interface Props {
  source: SourceInfo;
}

const SourceReference: React.FC<Props> = ({ source }) => {
  return (
    <Card
      size="small"
      style={{
        marginBottom: 8,
        background: '#fafafa',
        border: '1px solid #f0f0f0',
      }}
      bodyStyle={{ padding: '10px 14px' }}
    >
      {/* Header: doc name + page + score + source tags */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 6,
          flexWrap: 'wrap',
        }}
      >
        <FileTextOutlined style={{ color: '#1677FF', fontSize: 14 }} />
        <Text strong style={{ fontSize: 13 }}>
          {source.document_name || '未知文档'}
        </Text>
        {source.page != null && (
          <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
            P{source.page}
          </Tag>
        )}
        {source.chunk_index != null && (
          <Tag color="default" style={{ fontSize: 11, margin: 0 }}>
            Chunk #{source.chunk_index}
          </Tag>
        )}
        <Text type="secondary" style={{ fontSize: 11, marginLeft: 'auto' }}>
          相关度: {(source.score * 100).toFixed(0)}%
        </Text>
      </div>

      {/* Source pathway tags */}
      {source.sources && source.sources.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          {source.sources.map((src) => (
            <Tag
              key={src}
              color={SOURCE_COLORS[src] || 'default'}
              style={{ fontSize: 10, lineHeight: '16px', marginRight: 4 }}
            >
              {src.toUpperCase()}
            </Tag>
          ))}
        </div>
      )}

      {/* Chunk text excerpt */}
      <Paragraph
        ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
        type="secondary"
        style={{ fontSize: 12, margin: 0, whiteSpace: 'pre-wrap' }}
      >
        {source.chunk_text}
      </Paragraph>
    </Card>
  );
};

export default SourceReference;
