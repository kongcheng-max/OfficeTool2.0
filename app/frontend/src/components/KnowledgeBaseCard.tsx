import React from 'react';
import { Popconfirm } from 'antd';
import {
  FileTextOutlined,
  FileOutlined,
  MessageOutlined,
  CalendarOutlined,
  TagsOutlined,
} from '@ant-design/icons';

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
  onGraph?: (id: string) => void;
  onDelete?: (id: string) => void;
  onTags?: (id: string) => void;
}

const formatDate = (raw: string) => {
  if (!raw) return '-';
  const d = new Date(raw);
  return isNaN(d.getTime()) ? '-' : d.toLocaleDateString('zh-CN');
};

/** 停止事件冒泡到卡片，避免触发整卡的“进入” */
const stop = (e: React.MouseEvent) => e.stopPropagation();

const KnowledgeBaseCard: React.FC<KnowledgeBaseCardProps> = ({
  id,
  name,
  description,
  documentCount,
  qaCount = 0,
  tags,
  createdAt,
  onEnter,
  onManage,
  onGraph,
  onDelete,
  onTags,
}) => {
  return (
    <div className="kb-card" onClick={() => onEnter(id)} role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') onEnter(id); }}>
      <div className="kb-card__stripe" />
      <div className="kb-card__body">
        {/* 图标 + 标题 */}
        <div className="kb-card__head">
          <div className="kb-card__icon"><FileTextOutlined /></div>
          <div className="kb-card__titlewrap">
            <h3 className="kb-card__title" title={name}>{name}</h3>
            {description && <p className="kb-card__desc" title={description}>{description}</p>}
          </div>
        </div>

        {/* 元信息 */}
        <div className="kb-card__meta">
          <span><FileOutlined /> {documentCount} 文档</span>
          <span><MessageOutlined /> {qaCount} 问答</span>
          <span><CalendarOutlined /> {formatDate(createdAt)}</span>
        </div>

        {/* 标签 */}
        {tags && tags.length > 0 && (
          <div className="kb-card__tags">
            {tags.map((t) => <span key={t} className="kb-chip">{t}</span>)}
          </div>
        )}

        <div className="kb-card__divider" />

        {/* 内联操作 */}
        <div className="kb-card__actions">
          <span
            className="kb-action kb-action--primary"
            onClick={(e) => { stop(e); onEnter(id); }}
          >
            进入
          </span>
          <span className="kb-sep" />
          <span className="kb-action" onClick={(e) => { stop(e); onManage(id); }}>文档管理</span>
          {onGraph && (
            <>
              <span className="kb-sep" />
              <span className="kb-action" onClick={(e) => { stop(e); onGraph(id); }}>知识图谱</span>
            </>
          )}
          {onDelete && (
            <>
              <span className="kb-sep" />
              <Popconfirm
                title="确定删除此知识库？所有文档将被删除且不可恢复"
                onConfirm={() => onDelete(id)}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <span className="kb-action kb-action--danger" onClick={stop}>删除</span>
              </Popconfirm>
            </>
          )}
        </div>

        {/* 标签管理 */}
        {onTags && (
          <div>
            <span className="kb-taglink" onClick={(e) => { stop(e); onTags(id); }}>
              <TagsOutlined /> 标签管理
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseCard;
