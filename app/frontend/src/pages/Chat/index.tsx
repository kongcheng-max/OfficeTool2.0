import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Input,
  Button,
  Typography,
  Spin,
  Empty,
  Space,
  List,
  Popconfirm,
  App,
} from 'antd';
import {
  SendOutlined,
  PlusOutlined,
  DeleteOutlined,
  MessageOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import ChatMessage from '../../components/ChatMessage';
import { chatStream } from '../../api/qa';
import type { SourceInfo } from '../../api/qa';
import { useKBStore } from '../../stores/kbStore';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// ── Types ──────────────────────────────────────────────────

interface Message {
  role: 'user' | 'ai';
  content: string;
  sources?: SourceInfo[];
  confidence?: number;
  loading?: boolean;
}

interface Conversation {
  id: string;
  title: string;          // first question, truncated
  messages: Message[];
  createdAt: string;       // ISO
}

const SIDEBAR_WIDTH = 280;
const LS_PREFIX = 'officetool_convs_';

function loadConversations(kbId: string): Conversation[] {
  try {
    const raw = localStorage.getItem(LS_PREFIX + kbId);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(kbId: string, convs: Conversation[]) {
  // keep max 50 conversations
  const trimmed = convs.slice(0, 50);
  localStorage.setItem(LS_PREFIX + kbId, JSON.stringify(trimmed));
}

// ── Component ──────────────────────────────────────────────

const Chat: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const kbId = id || '';
  const { message: msgApi } = App.useApp();
  const { list } = useKBStore();
  const currentKB = list.find((kb) => kb.id === kbId);

  const [conversations, setConversations] = useState<Conversation[]>(() =>
    loadConversations(kbId),
  );
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Current conversation messages (derived)
  const messages: Message[] = useMemo(() => {
    const conv = conversations.find((c) => c.id === activeConvId);
    return conv?.messages ?? [];
  }, [conversations, activeConvId]);

  // Persist to localStorage after every change
  useEffect(() => {
    saveConversations(kbId, conversations);
  }, [kbId, conversations]);

  // Reload when kbId changes
  useEffect(() => {
    const convs = loadConversations(kbId);
    setConversations(convs);
    setActiveConvId(null);
    abortRef.current?.abort();
    setLoading(false);
  }, [kbId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Helpers ────────────────────────────────────────────

  const updateConversation = useCallback(
    (convId: string, updater: (c: Conversation) => Conversation) => {
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? updater(c) : c)),
      );
    },
    [],
  );

  // ── Send message ────────────────────────────────────────

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setLoading(true);

    const userMsg: Message = { role: 'user', content: question };
    const aiMsg: Message = { role: 'ai', content: '', loading: true };

    let convId = activeConvId;

    // Ensure we have a conversation
    if (!convId) {
      convId = crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36);
      const newConv: Conversation = {
        id: convId,
        title: question.slice(0, 40) + (question.length > 40 ? '…' : ''),
        messages: [userMsg, aiMsg],
        createdAt: new Date().toISOString(),
      };
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(convId);
    } else {
      updateConversation(convId, (c) => ({
        ...c,
        messages: [...c.messages, userMsg, aiMsg],
        // update title if empty/default
        title: c.title || question.slice(0, 40),
      }));
    }

    abortRef.current = chatStream(
      kbId,
      question,
      convId,
      // onChunk
      (text) => {
        updateConversation(convId!, (c) => {
          const msgs = [...c.messages];
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'ai') {
            msgs[msgs.length - 1] = {
              ...last,
              content: last.content + text,
              loading: false,
            };
          }
          return { ...c, messages: msgs };
        });
      },
      // onDone
      (sources, confidence, conversationId) => {
        updateConversation(convId!, (c) => {
          const msgs = [...c.messages];
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'ai') {
            msgs[msgs.length - 1] = {
              ...last,
              sources,
              confidence,
              loading: false,
            };
          }
          // update title from first question if missing
          return {
            ...c,
            id: conversationId || c.id,
            messages: msgs,
          };
        });
        // Sync conv id if BE returned a new one
        if (conversationId && conversationId !== convId) {
          setActiveConvId(conversationId);
          setConversations((prev) =>
            prev.map((c) =>
              c.id === convId ? { ...c, id: conversationId } : c,
            ),
          );
        }
        setLoading(false);
        abortRef.current = null;
      },
      // onError
      (error) => {
        updateConversation(convId!, (c) => {
          const msgs = [...c.messages];
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'ai') {
            msgs[msgs.length - 1] = {
              ...last,
              content: `❌ 请求失败：${error.message}`,
              loading: false,
            };
          }
          return { ...c, messages: msgs };
        });
        setLoading(false);
        abortRef.current = null;
      },
    );
  }, [input, loading, kbId, activeConvId, updateConversation]);

  const handleNewChat = () => {
    abortRef.current?.abort();
    setActiveConvId(null);
    setLoading(false);
  };

  const handleDeleteConv = (convId: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== convId));
    if (activeConvId === convId) {
      setActiveConvId(null);
      abortRef.current?.abort();
      setLoading(false);
    }
    // Tell BE to clear (fire-and-forget)
    fetch(`/api/v1/kb/${kbId}/chat/${convId}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
    }).catch(() => {});
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestions = [
    '这个知识库中有哪些文档？',
    '请帮我总结一下核心内容',
    '帮我搜索相关条款',
  ];

  // ── Render ───────────────────────────────────────────────

  return (
    <div style={{ display: 'flex', gap: 16, height: `calc(100vh - 64px - 48px - 48px)` }}>
      {/* ── Conversation Sidebar ── */}
      <div
        style={{
          width: SIDEBAR_WIDTH,
          flexShrink: 0,
          background: '#fff',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Sidebar Header */}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Text strong>对话列表</Text>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleNewChat}
          >
            新对话
          </Button>
        </div>

        {/* Conversation List */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {conversations.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无对话"
              style={{ marginTop: 40 }}
            />
          ) : (
            <List
              dataSource={conversations}
              renderItem={(conv) => (
                <div
                  key={conv.id}
                  onClick={() => {
                    abortRef.current?.abort();
                    setActiveConvId(conv.id);
                    setLoading(false);
                  }}
                  style={{
                    padding: '12px 16px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #fafafa',
                    background:
                      activeConvId === conv.id ? '#e6f4ff' : 'transparent',
                    borderLeft:
                      activeConvId === conv.id
                        ? '3px solid #1677FF'
                        : '3px solid transparent',
                    transition: 'all 0.2s',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <Space size={4} style={{ flex: 1, minWidth: 0 }}>
                      <MessageOutlined
                        style={{
                          color: activeConvId === conv.id ? '#1677FF' : '#8c8c8c',
                          fontSize: 12,
                        }}
                      />
                      <Text
                        ellipsis
                        style={{
                          fontSize: 13,
                          color: activeConvId === conv.id ? '#1677FF' : '#262626',
                        }}
                      >
                        {conv.title || '新对话'}
                      </Text>
                    </Space>
                    <Popconfirm
                      title="删除此对话？"
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDeleteConv(conv.id);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Popconfirm>
                  </div>
                  <Paragraph
                    type="secondary"
                    style={{
                      fontSize: 11,
                      margin: '4px 0 0 0',
                      color: '#8c8c8c',
                    }}
                  >
                    {conv.messages.length} 条消息 ·{' '}
                    {new Date(conv.createdAt).toLocaleDateString('zh-CN')}
                  </Paragraph>
                </div>
              )}
            />
          )}
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16,
          }}
        >
          <Title level={4} style={{ margin: 0 }} ellipsis>
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
          {!activeConvId || messages.length === 0 ? (
            <div style={{ textAlign: 'center', paddingTop: 80 }}>
              <Empty
                description={
                  activeConvId
                    ? '开始追问吧'
                    : '选择一个对话或创建新对话来开始提问'
                }
              >
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
                          // auto-create conversation if needed
                          setInput(q);
                          if (!activeConvId) {
                            handleNewChat();
                          }
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
    </div>
  );
};

export default Chat;
