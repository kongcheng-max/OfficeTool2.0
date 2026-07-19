import React from 'react';
import { useTheme } from '../theme/ThemeProvider';
import { sourceColors } from '../theme/tokens';
import type { SourceInfo } from '../api/qa';

interface Props {
  source: SourceInfo;
  index: number;
}

function formatRelevance(score: number) {
  if (!Number.isFinite(score)) return '0%';
  const percent = score <= 1 ? score * 100 : score;
  const clamped = Math.min(100, Math.max(0, percent));
  return `${clamped.toFixed(0)}%`;
}

const SOURCE_LABELS: Record<string, string> = {
  vector: '向量',
  bm25: '关键词',
  kg: '图谱',
};

/** 证据链节点：一处文档来源，挂在答案下方的时间线中 */
const SourceReference: React.FC<Props> = ({ source, index }) => {
  const { mode } = useTheme();
  const colors = sourceColors[mode];

  return (
    <div className="ot-rise" style={{ ...cardStyle, animationDelay: `${0.25 + index * 0.12}s` }}>
      <span style={nodeDot} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <span style={docIco}>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" />
          </svg>
        </span>
        <span style={docName}>{source.document_name || '未知文档'}</span>
        {source.score != null && (
          <span style={{ fontFamily: 'var(--f-mono)', fontSize: 12, fontWeight: 500, color: 'var(--success)' }}>
            相关度 {formatRelevance(source.score)}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 9, flexWrap: 'wrap' }}>
        {source.page != null && <span style={{ ...chip, background: 'var(--hover)', color: 'var(--ink-2)', fontFamily: 'var(--f-mono)' }}>p.{source.page}</span>}
        {source.chunk_index != null && <span style={{ ...chip, background: 'var(--hover)', color: 'var(--ink-2)', fontFamily: 'var(--f-mono)' }}>块 #{source.chunk_index}</span>}
        {source.sources?.map((src) => {
          const c = colors[src] || 'var(--ink-2)';
          return (
            <span key={src} style={{ ...chip, color: c, background: `color-mix(in srgb, ${c} 15%, transparent)` }}>
              {SOURCE_LABELS[src] || src.toUpperCase()}
            </span>
          );
        })}
      </div>

      {source.chunk_text && (
        <div style={excerpt}>{source.chunk_text}</div>
      )}
    </div>
  );
};

const cardStyle: React.CSSProperties = {
  position: 'relative',
  background: 'var(--paper)',
  border: '1px solid var(--line)',
  borderRadius: 'var(--r-md)',
  padding: '12px 14px',
  marginBottom: 10,
  boxShadow: 'var(--sh-sm)',
};

const nodeDot: React.CSSProperties = {
  position: 'absolute',
  left: -22,
  top: 16,
  width: 12,
  height: 12,
  borderRadius: '50%',
  background: 'var(--paper)',
  border: '2.5px solid var(--brand)',
  boxShadow: '0 0 0 4px var(--body)',
};

const docIco: React.CSSProperties = {
  width: 26,
  height: 26,
  borderRadius: 7,
  background: 'var(--halo)',
  color: 'var(--brand)',
  display: 'grid',
  placeItems: 'center',
  flex: 'none',
};

const docName: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  fontSize: 13.5,
  fontWeight: 600,
  color: 'var(--ink)',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const chip: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  padding: '2px 8px',
  borderRadius: 6,
  letterSpacing: '.02em',
};

const excerpt: React.CSSProperties = {
  marginTop: 9,
  fontSize: 12.5,
  color: 'var(--ink-2)',
  lineHeight: 1.6,
  borderLeft: '2px solid var(--divider)',
  paddingLeft: 10,
  whiteSpace: 'pre-wrap',
};

export default SourceReference;
