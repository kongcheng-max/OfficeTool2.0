import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Input, Button, Typography, Spin, Empty, Space, Select, App } from 'antd';
import { SendOutlined, PlusOutlined, ClearOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import ChatMessage from '../../components/ChatMessage';
import { askQuestionStream } from '../../api/qa';
import type { SourceInfo } from '../../api/qa';
import { useKBStore } from '../../stores/kbStore';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Message {
  role: 'user' | 'ai';
  content: string;
  sources?: SourceInfo[];
  confidence?: number;
  loading?: boolean;
}

const Chat: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const kbId = id || '';
  const { message: msgApi } = App.useApp();
  const { list } = useKBStore();
  const currentKB = list.find((kb) => kb.id === kbId);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setLoading(true);

    // Append user message
    const userMsg: Message = { role: 'user', content: question };
    const aiMsg: Message = { role: 'ai', content: '', loading: true };
    setMessages((prev) => [...prev, userMsg, aiMsg]);

    abortRef.current = askQuestionStream(
      kbId,
      question,
      // onChunk
      (text) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'ai') {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + text,
              loading: false,
            };
          }
          return updated;
        });
      },
      // onDone
      (sources, confidence, conversationId) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'ai') {
            updated[updated.length - 1] = {
              ...last,
              sources,
              confidence,
              loading: false,
            };
          }
          return updated;
        });
        setLoading(false);
        abortRef.current = null;
      },
      // onError
      (error) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'ai') {
            updated[updated.length - 1] = {
              ...last,
              content: `❌ 请求失败：${error.message}`,
              loading: false,
            };
          }
          return updated;
        });
        setLoading(false);
        abortRef.current = null;
      },
    );
  }, [input, loading, kbId]);

  const handleNewChat = () => {
    // Cancel any ongoing stream
    abortRef.current?.abort();
    setMessages([]);
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Suggested questions
  const suggestions = ['这个知识库中有哪些文档？', '请帮我总结一下核心内容', '帮我搜索相关条款'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: `calc(100vh - 64px - 48px - 48px)` }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          智能问答 — {currentKB?.name || `知识库 #${kbId}`}
        </Title>
        <Button icon={<PlusOutlined />} onClick={handleNewChat} disabled={loading}>
          新对话
        </Button>
      </div>

      {/* Messages Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
          marginBottom: 16,
          padding: 24,
        }}
      >
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <Empty description="开始提问吧">
              <div style={{ marginTop: 16 }}>
                <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                  试试这些问题：
                </Text>
                <Space direction="vertical" size={8}>
                  {suggestions.map((q, i) => (
                    <Button
                      key={i}
                      type="dashed"
                      onClick={() => {
                        setInput(q);
                      }}
                    >
                      {q}
                    </Button>
                  ))}
                </Space>
              </div>
            </Empty>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                role={msg.role}
                content={msg.content}
                sources={msg.sources}
                confidence={msg.confidence}
                loading={msg.loading}
              />
            ))}
            {loading && messages[messages.length - 1]?.role === 'ai' && (
              <div style={{ padding: '8px 16px' }}>
                <Text type="secondary">
                  <Spin size="small" /> AI 正在生成回答…
                </Text>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div
        style={{
          display: 'flex',
          gap: 12,
          alignItems: 'flex-end',
          padding: '12px 16px',
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
        }}
      >
        <TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题… (Enter 发送，Shift+Enter 换行)"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={loading}
          style={{ flex: 1, border: 'none' }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          disabled={!input.trim()}
        >
          发送
        </Button>
      </div>
    </div>
  );
};

export default Chat;
