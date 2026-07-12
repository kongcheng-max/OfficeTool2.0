import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Input,
  Button,
  Typography,
  Spin,
  Empty,
  Space,
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
import { Stagger, StaggerItem } from '../../components/motion/FadeIn';
import { chatStream } from '../../api/qa';
import type { SourceInfo } from '../../api/qa';
import { useKBStore } from '../../stores/kbStore';

const { Text } = Typography;
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
    <div style={{ display: 'flex', gap: 16, height: '100%', padding: 20, minHeight: 0 }}>
      {/* ── Conversation Sidebar ── */}
      <div
        style={{
          width: SIDEBAR_WIDTH,
          flexShrink: 0,
          background: 'var(--paper)',
          borderRadius: 14,
          border: '1px solid var(--line)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Sidebar Header */}
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--divider)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 15 }}>会话</span>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleNewChat}>
            新会话
          </Button>
        </div>

        {/* Conversation List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
          {conversations.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无会话"
              style={{ marginTop: 40 }}
            />
          ) : (
            <Stagger>
              {conversations.map((conv) => {
              const active = activeConvId === conv.id;
              return (
                <StaggerItem key={conv.id}>
                <div
                  onClick={() => {
                    abortRef.current?.abort();
                    setActiveConvId(conv.id);
                    setLoading(false);
                  }}
                  style={{
                    padding: '10px 12px',
                    cursor: 'pointer',
                    borderRadius: 10,
                    marginBottom: 2,
                    background: active ? 'var(--active)' : 'transparent',
                    transition: 'background .14s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
                      <MessageOutlined style={{ color: active ? 'var(--brand)' : 'var(--ink-3)', fontSize: 12 }} />
                      <span
                        style={{
                          fontSize: 13.5,
                          fontWeight: active ? 600 : 500,
                          color: active ? 'var(--brand)' : 'var(--ink)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {conv.title || '新会话'}
                      </span>
                    </div>
                    <Popconfirm
                      title="删除此会话？"
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
                  <div style={{ fontSize: 11.5, margin: '4px 0 0 18px', color: 'var(--ink-3)' }}>
                    {conv.messages.length} 条 · {new Date(conv.createdAt).toLocaleDateString('zh-CN')}
                  </div>
                </div>
                </StaggerItem>
              );
            })}
            </Stagger>
          )}
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Messages Area */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            background: 'var(--paper)',
            borderRadius: 14,
            border: '1px solid var(--line)',
            marginBottom: 14,
            padding: 26,
            minHeight: 0,
          }}
        >
          {!activeConvId || messages.length === 0 ? (
            <div style={{ textAlign: 'center', paddingTop: 72, maxWidth: 460, margin: '0 auto' }}>
              <span className="ot-mark" style={{ width: 56, height: 56, borderRadius: 16, display: 'inline-block', marginBottom: 18 }} />
              <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 20, color: 'var(--ink)' }}>
                向「{currentKB?.name || '知识库'}」提问
              </div>
              <Text type="secondary" style={{ display: 'block', margin: '8px 0 20px' }}>
                每个回答都会连回它引用的文档来源
              </Text>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                {suggestions.map((q, i) => (
                  <Button
                    key={i}
                    block
                    onClick={() => {
                      setInput(q);
                      if (!activeConvId) handleNewChat();
                    }}
                    style={{ textAlign: 'left', height: 'auto', padding: '10px 14px' }}
                  >
                    {q}
                  </Button>
                ))}
              </Space>
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
                <div style={{ paddingLeft: 46 }}>
                  <Text type="secondary">
                    <Spin size="small" /> 正在生成回答…
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
            gap: 10,
            alignItems: 'flex-end',
            padding: '10px 10px 10px 16px',
            background: 'var(--paper)',
            borderRadius: 14,
            border: '1px solid var(--line)',
            boxShadow: 'var(--sh-sm)',
          }}
        >
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题…（Enter 发送，Shift+Enter 换行）"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            variant="borderless"
            style={{ flex: 1 }}
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
