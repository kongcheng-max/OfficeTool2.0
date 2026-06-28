import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table,
  Button,
  Tooltip,
  Typography,
  Space,
  Popconfirm,
  Modal,
  Select,
  Tag,
  Tabs,
  Upload,
  App,
} from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  EyeOutlined,
  InboxOutlined,
  FileZipOutlined,
  FolderOpenOutlined,
  SwapOutlined,
  TagOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import {
  getDocumentList,
  deleteDocument,
  batchUploadDocuments,
  importZip,
  type DocumentItem,
  type DocStatus,
  type BatchUploadResponse,
} from '../../api/document';
import { getTags, assignTags, type TagItem } from '../../api/tag';
import DocumentStatusBadge from '../../components/DocumentStatusBadge';
import DocumentUpload from '../../components/DocumentUpload';
import DocumentPreview from '../../components/DocumentPreview';

const { Title, Text } = Typography;
const { Dragger } = Upload;

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const Documents: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const kbId = id || '';
  const { message } = App.useApp();

  const [data, setData] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<DocStatus | undefined>();
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);

  // ── Batch tag assignment state ──────────────────────────
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [tagModalOpen, setTagModalOpen] = useState(false);
  const [allTags, setAllTags] = useState<TagItem[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  // ── Batch upload state ─────────────────────────────────
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [batchResult, setBatchResult] = useState<BatchUploadResponse | null>(null);
  const [batchUploading, setBatchUploading] = useState(false);

  const folderInputRef = useRef<HTMLInputElement>(null);

  // BUG-041: set directory attributes via ref for cross-browser reliability
  useEffect(() => {
    const el = folderInputRef.current;
    if (el) {
      el.setAttribute('webkitdirectory', '');
      el.setAttribute('directory', '');
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDocumentList(kbId, { page, page_size: 20, status: statusFilter });
      setData(res.items);
      setTotal(res.total);
    } catch (e: any) {
      console.debug('[BUG-011] fetchData failed:', e?.message || e);
    }
    setLoading(false);
  }, [kbId, page, statusFilter]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(), 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(kbId, docId);
      message.success('文档已删除');
      fetchData();
    } catch (e: any) {
      console.debug('[BUG-011] handleDelete failed:', e?.message || e);
    }
  };

  const handleBatchUpload = async () => {
    if (batchFiles.length === 0) return;
    setBatchUploading(true);
    try {
      const res = await batchUploadDocuments(kbId, batchFiles);
      setBatchResult(res);
      message.success(`批量上传完成：成功 ${res.success_count}，失败 ${res.failed_count}`);
      fetchData();
    } catch (e: any) {
      console.debug('[BUG-011] handleBatchUpload failed:', e?.message || e);
    }
    setBatchUploading(false);
  };

  const handleZipImport = async (file: File) => {
    setBatchUploading(true);
    try {
      const res = await importZip(kbId, file);
      setBatchResult(res);
      message.success(`ZIP 导入完成：成功 ${res.success_count}，失败 ${res.failed_count}`);
      fetchData();
    } catch (e: any) {
      console.debug('[BUG-011] handleZipImport failed:', e?.message || e);
    }
    setBatchUploading(false);
  };

  const columns: ColumnsType<DocumentItem> = [
    {
      title: '序号',
      key: 'index',
      width: 60,
      render: (_: unknown, __: DocumentItem, idx: number) => (page - 1) * 20 + idx + 1,
    },
    {
      title: '文件名',
      dataIndex: 'original_filename',
      ellipsis: true,
      render: (text, record) => (
        <a onClick={() => setPreviewDocId(record.id)}>
          📄 {text || record.filename}
        </a>
      ),
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      width: 100,
      render: (size) => formatFileSize(size),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 120,
      render: (status: DocStatus) => <DocumentStatusBadge status={status} />,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      width: 200,
      render: (tags: TagItem[] | undefined) => (
        <Space size={4} wrap>
          {(tags || []).slice(0, 3).map((t) => (
            <Tag key={t.id} color={t.color}>{t.name}</Tag>
          ))}
          {(tags || []).length > 3 && <Tag>+{tags!.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: '块数',
      dataIndex: 'chunk_count',
      width: 80,
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      width: 120,
      render: (text) =>
        text ? new Date(text).toLocaleDateString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 170,
      render: (_: unknown, record: DocumentItem) => (
        <Space>
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => setPreviewDocId(record.id)}
            title="预览"
          />
          <Tooltip title="预览、替换与版本管理">
            <Button
              type="text"
              icon={<SwapOutlined />}
              onClick={() => setPreviewDocId(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此文档？"
            description="删除后不可恢复"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          文档管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData}>
            刷新
          </Button>
          <Button
            icon={<UploadOutlined />}
            onClick={() => setBatchModalOpen(true)}
          >
            批量上传
          </Button>
          <input
            ref={folderInputRef}
            type="file"
            style={{ display: 'none' }}
            onChange={(e) => {
              const allFiles = Array.from(e.target.files || []);
              const zipFiles = allFiles.filter(f => f.name.toLowerCase().endsWith('.zip'));
              const otherFiles = allFiles.filter(f => !f.name.toLowerCase().endsWith('.zip'));
              // .zip 自动走 ZIP 导入管道
              zipFiles.forEach(f => {
                handleZipImport(f);
                message.info(`已提交 ZIP 导入: ${f.name}`);
              });
              // 其他格式走批量上传
              if (otherFiles.length > 0) {
                setBatchFiles(otherFiles);
                setBatchModalOpen(true);
              }
              e.target.value = '';
            }}
          />
          <Button
            icon={<FolderOpenOutlined />}
            onClick={() => folderInputRef.current?.click()}
          >
            文件夹上传
          </Button>
          <Tooltip title={selectedRowKeys.length === 0 ? '请先勾选左侧文档行' : undefined}>
            {/* BUG-040: span wrapper so Tooltip can fire on a disabled button */}
            <span>
              <Button
                icon={<TagOutlined />}
                disabled={selectedRowKeys.length === 0}
                onClick={() => setTagModalOpen(true)}
              >
                批量分配标签
                {selectedRowKeys.length > 0 ? ` (${selectedRowKeys.length})` : ''}
              </Button>
            </span>
          </Tooltip>
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => setUploadModalOpen(true)}
          >
            上传文档
          </Button>
        </Space>
      </div>

      <div style={{ marginBottom: 16, display: 'flex', gap: 16 }}>
        <Select
          placeholder="按状态筛选"
          allowClear
          style={{ width: 140 }}
          value={statusFilter}
          onChange={(val) => {
            setStatusFilter(val);
            setPage(1);
          }}
          options={[
            { value: 'ready', label: '✅ 就绪' },
            { value: 'processing', label: '⏳ 解析中' },
            { value: 'uploaded', label: '📤 已上传' },
            { value: 'error', label: '❌ 失败' },
          ]}
        />
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as string[]),
        }}
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      {/* ── Single Upload Modal ── */}
      <Modal
        title="上传文档"
        open={uploadModalOpen}
        onCancel={() => setUploadModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <DocumentUpload
          kbId={kbId}
          onSuccess={() => fetchData()}
          onClose={() => setUploadModalOpen(false)}
        />
      </Modal>

      {/* ── Batch Upload / ZIP Import Modal ── */}
      <Modal
        title="批量上传"
        open={batchModalOpen}
        onCancel={() => {
          setBatchModalOpen(false);
          setBatchFiles([]);
          setBatchResult(null);
        }}
        footer={null}
        width={560}
        destroyOnClose
      >
        <Tabs
          items={[
            {
              key: 'batch',
              label: '多文件上传',
              children: (
                <div>
                  <Dragger
                    multiple
                    accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.md,.pptx,.ppt,.csv,.json,.html,.xml,.jpg,.jpeg,.png,.bmp,.tiff,.tif,.webp"
                    beforeUpload={(file) => {
                      setBatchFiles((prev) => [...prev, file]);
                      return false;
                    }}
                    showUploadList
                    fileList={batchFiles.map((f: File, i: number) => ({
                      uid: `${i}-${f.name}`,
                      name: f.name,
                      status: 'done' as const,
                    }))}
                    onRemove={(file) => {
                      setBatchFiles((prev) =>
                        prev.filter((_, i) => `${i}-${prev[i].name}` !== file.uid),
                      );
                    }}
                  >
                    <p className="ant-upload-drag-icon">
                      <InboxOutlined />
                    </p>
                    <p className="ant-upload-text">点击或拖拽文件到此区域</p>
                    <p className="ant-upload-hint">
                      支持 PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, JSON 等
                    </p>
                  </Dragger>
                  <Button
                    type="primary"
                    onClick={handleBatchUpload}
                    loading={batchUploading}
                    disabled={batchFiles.length === 0}
                    block
                    style={{ marginTop: 16 }}
                  >
                    上传 {batchFiles.length} 个文件
                  </Button>
                </div>
              ),
            },
            {
              key: 'zip',
              label: 'ZIP 导入',
              children: (
                <div>
                  <Dragger
                    accept=".zip"
                    beforeUpload={(file) => {
                      handleZipImport(file);
                      return false;
                    }}
                    showUploadList={false}
                  >
                    <p className="ant-upload-drag-icon">
                      <FileZipOutlined />
                    </p>
                    <p className="ant-upload-text">点击或拖拽 ZIP 文件</p>
                    <p className="ant-upload-hint">
                      自动解压并导入包内支持的文件格式
                    </p>
                  </Dragger>
                </div>
              ),
            },
          ]}
        />

        {/* Batch result */}
        {batchResult && (
          <div style={{ marginTop: 16, padding: 12, background: '#fafafa', borderRadius: 8 }}>
            <Text strong>结果：</Text>
            <Space size={16} style={{ marginLeft: 8 }}>
              <Text style={{ color: '#52C41A' }}>✅ 成功 {batchResult.success_count}</Text>
              <Text style={{ color: '#FF4D4F' }}>❌ 失败 {batchResult.failed_count}</Text>
              <Text type="secondary">⏭️ 跳过 {batchResult.skipped_count}</Text>
            </Space>
          </div>
        )}
      </Modal>

      {/* ── Batch Tag Assignment Modal ── */}
      <Modal
        title="批量分配标签"
        open={tagModalOpen}
        onCancel={() => {
          setTagModalOpen(false);
          setSelectedTagIds([]);
        }}
        onOk={async () => {
          if (selectedTagIds.length === 0) {
            message.warning('请选择至少一个标签');
            return;
          }
          try {
            await assignTags(kbId, selectedTagIds, selectedRowKeys);
            message.success(`已为 ${selectedRowKeys.length} 个文档分配标签`);
            setTagModalOpen(false);
            setSelectedTagIds([]);
            setSelectedRowKeys([]);
            fetchData();
          } catch (e: any) {
            message.error(`分配失败：${e?.message || '未知错误'}`);
          }
        }}
        okText="确定分配"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ marginBottom: 16 }}>
          <Text>已选择 <Text strong>{selectedRowKeys.length}</Text> 个文档</Text>
        </div>
        <Select
          mode="multiple"
          placeholder="选择标签"
          style={{ width: '100%' }}
          value={selectedTagIds}
          onChange={(val) => setSelectedTagIds(val)}
          onFocus={async () => {
            if (allTags.length === 0) {
              try {
                const tags = await getTags(kbId);
                setAllTags(tags);
              } catch (e: any) {
                message.error(`获取标签失败：${e?.message || '未知错误'}`);
              }
            }
          }}
          options={allTags.map((t) => ({
            value: t.id,
            label: t.name,
          }))}
        />
      </Modal>

      {/* ── Document Preview Drawer ── */}
      {previewDocId && (
        <DocumentPreview
          kbId={kbId}
          docId={previewDocId}
          open={!!previewDocId}
          onClose={() => setPreviewDocId(null)}
        />
      )}
    </div>
  );
};

export default Documents;
