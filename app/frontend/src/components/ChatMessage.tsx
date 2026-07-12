import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SourceReference from './SourceReference';
import type { SourceInfo } from '../api/qa';

interface Props {
  role: 'user' | 'ai';
  content: string;
  sources?: SourceInfo[];
  confidence?: number;
  loading?: boolean;
}

/** 置信度分档：高 / 中 / 低 → 段数 + 色 + 文案 */
function confidenceLevel(c: number) {
  if (c >= 0.8) return { segs: 4, color: 'var(--success)', label: '高' };
  if (c >= 0.6) return { segs: 3, color: 'var(--warning)', label: '中' };
  if (c >= 0.4) return { segs: 2, color: 'var(--warning)', label: '中' };
  return { segs: 1, color: 'var(--danger)', label: '低' };
}

const ChatMessage: React.FC<Props> = ({ role, content, sources, confidence, loading }) => {
  const isAI = role === 'ai';

  // ── 用户消息：右对齐气泡 ──
  if (!isAI) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 22 }}>
        <div style={userBubble}>{content}</div>
      </div>
    );
  }

  // ── AI 消息：头像 + 答案 + 证据链 ──
  const lvl = confidence != null && confidence > 0 ? confidenceLevel(confidence) : null;

  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: 26 }}>
      <div style={aiAvatar}>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" strokeWidth="2.2">
          <path d="M12 3v3M5 8h14v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z" />
          <circle cx="9.5" cy="13" r="1.1" fill="#fff" stroke="none" />
          <circle cx="14.5" cy="13" r="1.1" fill="#fff" stroke="none" />
        </svg>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 名称 + 置信度计量条 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 13.5, color: 'var(--ink)' }}>
            OfficeTool
          </span>
          {lvl && (
            <span style={confPill}>
              置信度
              <span style={{ display: 'inline-flex', gap: 2 }}>
                {[0, 1, 2, 3].map((i) => (
                  <i key={i} style={{ width: 4, height: 10, borderRadius: 1, background: i < lvl.segs ? lvl.color : 'var(--divider)' }} />
                ))}
              </span>
              <b style={{ color: lvl.color, fontWeight: 600 }}>{lvl.label}</b>
            </span>
          )}
        </div>

        {/* 答案正文 */}
        <div style={answerBox}>
          {content ? (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          ) : loading ? (
            <span style={{ color: 'var(--ink-3)' }}>思考中…</span>
          ) : null}
        </div>

        {/* 证据链 */}
        {sources && sources.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div style={evTitle}>
              证据链 · {sources.length} 处来源
              <span style={{ height: 1, flex: 1, background: 'var(--divider)' }} />
            </div>
            <div style={evTrack}>
              {sources.map((s, i) => (
                <SourceReference key={i} source={s} index={i} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const userBubble: React.CSSProperties = {
  maxWidth: '80%',
  background: 'var(--brand)',
  color: 'var(--on-brand)',
  fontSize: 14.5,
  fontWeight: 500,
  padding: '11px 16px',
  borderRadius: '14px 14px 4px 14px',
  boxShadow: 'var(--sh-sm)',
  lineHeight: 1.7,
  whiteSpace: 'pre-wrap',
};

const aiAvatar: React.CSSProperties = {
  width: 34,
  height: 34,
  borderRadius: 10,
  flex: 'none',
  marginTop: 2,
  background: 'linear-gradient(150deg, var(--brand-2), var(--brand-strong))',
  display: 'grid',
  placeItems: 'center',
  boxShadow: 'var(--sh-sm)',
};

const confPill: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  fontSize: 11.5,
  color: 'var(--ink-2)',
  padding: '2px 8px 2px 6px',
  borderRadius: 999,
  background: 'var(--paper)',
  border: '1px solid var(--line)',
};

const answerBox: React.CSSProperties = {
  background: 'var(--paper)',
  border: '1px solid var(--line)',
  borderRadius: '4px 14px 14px 14px',
  padding: '15px 17px',
  color: 'var(--ink)',
  boxShadow: 'var(--sh-sm)',
};

const evTitle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--ink-2)',
  letterSpacing: '.04em',
  marginBottom: 12,
};

const evTrack: React.CSSProperties = {
  position: 'relative',
  paddingLeft: 22,
  borderLeft: '2px solid var(--divider)',
  marginLeft: 5,
};

export default ChatMessage;
