import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Typography, Tag } from 'antd';
import { RobotOutlined, UserOutlined } from '@ant-design/icons';
import SourceReference from './SourceReference';
import type { SourceInfo } from '../api/qa';

const { Text } = Typography;

interface Props {
  role: 'user' | 'ai';
  content: string;
  sources?: SourceInfo[];
  confidence?: number;
  loading?: boolean;
}

const ChatMessage: React.FC<Props> = ({
  role,
  content,
  sources,
  confidence,
  loading,
}) => {
  const isAI = role === 'ai';

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        marginBottom: 24,
        flexDirection: role === 'user' ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: isAI ? '#1677FF' : '#52C41A',
          color: '#fff',
          fontSize: 18,
          flexShrink: 0,
        }}
      >
        {isAI ? <RobotOutlined /> : <UserOutlined />}
      </div>

      {/* Bubble */}
      <div
        style={{
          maxWidth: '75%',
          padding: '12px 16px',
          borderRadius: 12,
          background: isAI ? '#fff' : '#1677FF',
          color: isAI ? '#262626' : '#fff',
          boxShadow: isAI
            ? '0 1px 4px rgba(0,0,0,0.08)'
            : 'none',
          lineHeight: 1.8,
        }}
      >
        {content ? (
          isAI ? (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          ) : (
            <Text style={{ color: '#fff' }}>{content}</Text>
          )
        ) : loading ? (
          <Text type="secondary">思考中…</Text>
        ) : null}

        {/* Sources */}
        {sources && sources.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {sources.map((s, i) => (
              <SourceReference key={i} source={s} />
            ))}
          </div>
        )}

        {/* Confidence */}
        {confidence != null && confidence > 0 && (
          <div style={{ marginTop: 8 }}>
            <Tag
              color={
                confidence >= 0.8
                  ? 'green'
                  : confidence >= 0.6
                    ? 'orange'
                    : 'red'
              }
              style={{ fontSize: 12 }}
            >
              置信度: {(confidence * 100).toFixed(0)}%
            </Tag>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
