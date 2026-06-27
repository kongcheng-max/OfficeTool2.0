import React, { useEffect, useState, useCallback } from 'react';
import {
  Table,
  Button,
  Typography,
  Space,
  Popconfirm,
  Modal,
  Input,
  Select,
  App,
} from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import {
  getDocumentList,
  deleteDocument,
  type DocumentItem,
  type DocStatus,
} from '../../api/document';
import DocumentStatusBadge from '../../components/DocumentStatusBadge';
import DocumentUpload from '../../components/DocumentUpload';

const { Title } = Typography;

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

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getDocumentList(kbId, {
        page,
        page_size: 20,
        status: statusFilter,
      });
      setData(res.items);
      setTotal(res.total);
    } catch {
      // handled
    }
    setLoading(false);
  }, [kbId, page, statusFilter]);

  useEffect(() => {
    fetchData();
    // polling every 5s when there are processing items
    const interval = setInterval(() => {
      fetchData();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(kbId, docId);
      message.success('文档已删除');
      fetchData();
    } catch {
      // handled
    }
  };

  const columns: ColumnsType<DocumentItem> = [
    {
      title: '#',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: '文件名',
      dataIndex: 'original_filename',
      ellipsis: true,
      render: (text, record) => <span>📄 {text || record.filename}</span>,
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
      width: 100,
      render: (_: unknown, record: DocumentItem) => (
        <Space>
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
            { value: 'error', label: '❌ 失败' },
          ]}
        />
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      <Modal
        title="上传文档"
        open={uploadModalOpen}
        onCancel={() => setUploadModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <DocumentUpload
          kbId={kbId}
          onSuccess={() => {
            fetchData();
          }}
          onClose={() => setUploadModalOpen(false)}
        />
      </Modal>
    </div>
  );
};

export default Documents;
