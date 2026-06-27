import React, { useEffect, useState } from 'react';
import {
  Row,
  Col,
  Typography,
  Button,
  Modal,
  Input,
  Form,
  Spin,
  Empty,
  Popconfirm,
  App,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useKBStore } from '../../stores/kbStore';
import { createKB, deleteKB, type KnowledgeBaseItem } from '../../api/kb';
import KnowledgeBaseCard from '../../components/KnowledgeBaseCard';

const { Title } = Typography;
const { TextArea } = Input;

const KnowledgeBase: React.FC = () => {
  const { list, loading, fetchList } = useKBStore();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const handleCreate = async (values: { name: string; description?: string }) => {
    setCreating(true);
    try {
      await createKB(values);
      message.success('知识库创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchList();
    } catch {
      // handled by interceptor
    }
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteKB(id);
      message.success('知识库已删除');
      fetchList();
    } catch {
      // handled by interceptor
    }
  };

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
          我的知识库
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          创建知识库
        </Button>
      </div>

      {loading ? (
        <Spin style={{ display: 'block', padding: 80 }} />
      ) : list.length === 0 ? (
        <Empty description="暂无知识库">
          <Button type="primary" onClick={() => setModalOpen(true)}>
            创建第一个知识库
          </Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {list.map((kb: KnowledgeBaseItem) => (
            <Col xs={24} sm={12} lg={8} key={kb.id}>
              <KnowledgeBaseCard
                id={kb.id}
                name={kb.name}
                description={kb.description}
                documentCount={kb.doc_count || kb.document_count || 0}
                qaCount={kb.qa_count || 0}
                chunkCount={kb.chunk_count || 0}
                createdAt={kb.created_at}
                onEnter={(id) => navigate(`/kb/${id}/chat`)}
                onManage={(id) => navigate(`/kb/${id}/documents`)}
              />
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="创建知识库"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[{ required: true, message: '请输入知识库名称' }]}
          >
            <Input placeholder="例如：销售合同库、技术文档库" maxLength={60} />
          </Form.Item>
          <Form.Item name="description" label="描述（选填）">
            <TextArea rows={3} placeholder="简要描述该知识库的用途" maxLength={200} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={creating} block>
              创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgeBase;
