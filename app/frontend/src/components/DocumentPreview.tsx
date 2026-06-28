import React, { useEffect, useState } from 'react';
import {
  Drawer,
  Descriptions,
  Tag,
  Typography,
  Space,
  List,
  Spin,
  Empty,
  Select,
  Button,
  Modal,
  Upload,
  App,
  Input,
} from 'antd';
import {
  FileTextOutlined,
  ClockCircleOutlined,
  TagOutlined,
  HistoryOutlined,
  DownloadOutlined,
  SwapOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import {
  getDocumentDetail,
  getDocumentVersions,
  replaceDocument,
  type DocumentDetail,
  type DocumentVersion,
} from '../api/document';
import { getTags, assignTags, unassignTags, type TagItem } from '../api/tag';
import DocumentStatusBadge from './DocumentStatusBadge';

const { Text, Title } = Typography;
const { TextArea } = Input;

interface Props {
  kbId: string;
  docId: string;
  open: boolean;
  onClose: () => void;
}

const formatFileSize = (bytes: number): string => {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const DocumentPreview: React.FC<Props> = ({ kbId, docId, open, onClose }) => {
  const { message } = App.useApp();
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [allTags, setAllTags] = useState<TagItem[]>([]);
  const [loading, setLoading] = useState(false);

  // ── Replace state ────────────────────────────────
  const [replaceModalOpen, setReplaceModalOpen] = useState(false);
  const [replaceNote, setReplaceNote] = useState('');

  useEffect(() => {
    if (!open || !docId) return;

    const load = async () => {
      setLoading(true);
      try {
        const [d, v, t] = await Promise.all([
          getDocumentDetail(kbId, docId),
          getDocumentVersions(kbId, docId).catch(() => [] as DocumentVersion[]),
          getTags(kbId).catch(() => [] as TagItem[]),
        ]);
        setDetail(d);
        setVersions(v);
        setAllTags(t);
      } catch {
        // handled
      }
      setLoading(false);
    };
    load();
  }, [open, docId, kbId]);

  const assignedTagIds = detail?.tags?.map((t) => t.id) ?? [];

  const handleTagChange = async (selectedIds: string[]) => {
    if (!detail) return;
    const added = selectedIds.filter((id) => !assignedTagIds.includes(id));
    const removed = assignedTagIds.filter((id) => !selectedIds.includes(id));

    try {
      if (added.length > 0) {
        await assignTags(kbId, added, [docId]);
      }
      if (removed.length > 0) {
        await unassignTags(kbId, removed, [docId]);
      }
      message.success('标签已更新');
      const d = await getDocumentDetail(kbId, docId);
      setDetail(d);
    } catch {
      // handled
    }
  };

  const downloadUrl = `/api/v1/kb/${kbId}/documents/${docId}/download`;
  const isPdf = detail?.mime_type === 'application/pdf';
  const isImage = detail?.mime_type?.startsWith('image/');

  return (
    <Drawer
      title={
        <Space>
          <FileTextOutlined />
          <span>文档预览</span>
        </Space>
      }
      placement="right"
      width={600}
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      {loading || !detail ? (
        <Spin style={{ display: 'block', padding: 60 }} />
      ) : (
        <>
          {/* Basic Info */}
          <Title level={5} style={{ marginBottom: 12 }}>
            {detail.original_filename || detail.filename}
          </Title>

          <Descriptions column={1} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label="状态">
              <DocumentStatusBadge status={detail.status} />
            </Descriptions.Item>
            <Descriptions.Item label="文件大小">
              {formatFileSize(detail.file_size)}
            </Descriptions.Item>
            <Descriptions.Item label="MIME 类型">
              {detail.mime_type || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="分块数">
              {detail.chunk_count}
            </Descriptions.Item>
            <Descriptions.Item label="上传时间">
              {detail.created_at
                ? new Date(detail.created_at).toLocaleString('zh-CN')
                : '-'}
            </Descriptions.Item>
            {detail.error_message && (
              <Descriptions.Item label="错误信息">
                <Text type="danger">{detail.error_message}</Text>
              </Descriptions.Item>
            )}
          </Descriptions>

          {/* Action buttons */}
          <Space style={{ marginBottom: 16 }}>
            <Button
              icon={<DownloadOutlined />}
              onClick={() => window.open(downloadUrl, '_blank')}
            >
              下载 / 预览源文件
            </Button>
            <Button
              type="primary"
              ghost
              icon={<SwapOutlined />}
              onClick={() => setReplaceModalOpen(true)}
            >
              上传新版本
            </Button>
          </Space>

          {/* Source Content Preview */}
          {(isPdf || isImage) && (
            <div style={{ marginBottom: 16, border: '1px solid #f0f0f0', borderRadius: 8, overflow: 'hidden' }}>
              <div style={{ background: '#fafafa', padding: '4px 12px', borderBottom: '1px solid #f0f0f0' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>源文件预览</Text>
              </div>
              {isPdf ? (
                <iframe
                  src={downloadUrl}
                  style={{ width: '100%', height: 400, border: 'none' }}
                  title="PDF Preview"
                />
              ) : (
                <div style={{ padding: 8, textAlign: 'center' }}>
                  <img
                    src={downloadUrl}
                    alt={detail.original_filename}
                    style={{ maxWidth: '100%', maxHeight: 400 }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Tags */}
          <Title level={5} style={{ marginBottom: 8 }}>
            <TagOutlined /> 标签
          </Title>
          <Select
            mode="multiple"
            style={{ width: '100%', marginBottom: 16 }}
            placeholder="选择标签…"
            value={assignedTagIds}
            onChange={handleTagChange}
            options={allTags.map((t) => ({
              value: t.id,
              label: (
                <Space size={4}>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: t.color,
                    }}
                  />
                  {t.name}
                </Space>
              ),
            }))}
          />

          {detail.tags && detail.tags.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              {detail.tags.map((t) => (
                <Tag key={t.id} color={t.color}>
                  {t.name}
                </Tag>
              ))}
            </div>
          )}

          {/* Version History */}
          <Title level={5} style={{ marginBottom: 8 }}>
            <HistoryOutlined /> 版本历史 ({versions.length})
          </Title>
          {versions.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无版本记录。点击「上传新版本」替换文档以创建版本快照。"
              style={{ marginBottom: 16 }}
            />
          ) : (
            <List
              size="small"
              dataSource={versions}
              style={{ marginBottom: 16 }}
              renderItem={(v) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag color="blue">v{v.version}</Tag>
                        <Text>{formatFileSize(v.file_size)}</Text>
                        <Text type="secondary">
                          <ClockCircleOutlined />{' '}
                          {new Date(v.created_at).toLocaleString('zh-CN')}
                        </Text>
                      </Space>
                    }
                    description={
                      v.change_note ? (
                        <Text type="secondary">{v.change_note}</Text>
                      ) : null
                    }
                  />
                </List.Item>
              )}
            />
          )}

          {/* ── Replace Document Modal ── */}
          <Modal
            title="上传新版本"
            open={replaceModalOpen}
            onCancel={() => setReplaceModalOpen(false)}
            footer={null}
            destroyOnClose
          >
            <Upload
              customRequest={async (opts: any) => {
                const { file, onSuccess, onError } = opts;
                try {
                  await replaceDocument(kbId, docId, file as File, replaceNote);
                  message.success(`文档已替换，版本快照已创建`);
                  onSuccess?.();
                  setReplaceModalOpen(false);
                  setReplaceNote('');
                  const [d, v] = await Promise.all([
                    getDocumentDetail(kbId, docId),
                    getDocumentVersions(kbId, docId).catch(() => [] as DocumentVersion[]),
                  ]);
                  setDetail(d);
                  setVersions(v);
                } catch (e: any) {
                  onError?.(e);
                  message.error(`替换失败: ${e?.message || '未知错误'}`);
                }
              }}
              accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.csv,.json,.html,.xml,.txt,.md,.jpg,.jpeg,.png,.bmp,.tiff,.tif,.webp"
              showUploadList={false}
            >
              <Button icon={<UploadOutlined />} block>选择文件替换</Button>
            </Upload>
            <TextArea
              placeholder="版本变更说明（选填）"
              value={replaceNote}
              onChange={(e) => setReplaceNote(e.target.value)}
              rows={2}
              style={{ marginTop: 12 }}
            />
          </Modal>
        </>
      )}
    </Drawer>
  );
};

export default DocumentPreview;
