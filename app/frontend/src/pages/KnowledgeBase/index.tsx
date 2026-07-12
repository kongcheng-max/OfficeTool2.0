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
  Space,
  Tag,
  List,
  Popconfirm,
  ColorPicker,
  App,
} from 'antd';
import {
  PlusOutlined,
  TagOutlined,
  DeleteOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useKBStore } from '../../stores/kbStore';
import { createKB, deleteKB, type KnowledgeBaseItem } from '../../api/kb';
import {
  getTags,
  getTagStats,
  createTag,
  deleteTag as deleteTagApi,
  type TagItem,
  type TagStat,
} from '../../api/tag';
import KnowledgeBaseCard from '../../components/KnowledgeBaseCard';
import { FadeIn } from '../../components/motion/FadeIn';

const { Title, Text } = Typography;
const { TextArea } = Input;

const KnowledgeBase: React.FC = () => {
  const { list, loading, fetchList } = useKBStore();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState('');
  const [form] = Form.useForm();

  const filteredList = list.filter((kb) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      kb.name.toLowerCase().includes(q) ||
      (kb.description || '').toLowerCase().includes(q)
    );
  });

  // ── Tag management state ─────────────────────────────
  const [tagModalKbId, setTagModalKbId] = useState<string | null>(null);
  const [tagModalKbName, setTagModalKbName] = useState('');
  const [tagList, setTagList] = useState<TagItem[]>([]);
  const [tagStats, setTagStats] = useState<TagStat[]>([]);
  const [tagLoading, setTagLoading] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState('#1890ff');

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

  // ── Tag management ───────────────────────────────────

  const openTagManager = async (kbId: string, kbName: string) => {
    setTagModalKbId(kbId);
    setTagModalKbName(kbName);
    setTagLoading(true);
    try {
      const [items, stats] = await Promise.all([
        getTags(kbId),
        getTagStats(kbId),
      ]);
      setTagList(items);
      setTagStats(stats);
    } catch {
      // handled
    }
    setTagLoading(false);
  };

  const handleCreateTag = async () => {
    if (!tagModalKbId || !newTagName.trim()) return;
    try {
      await createTag(tagModalKbId, { name: newTagName.trim(), color: newTagColor });
      message.success('标签创建成功');
      setNewTagName('');
      // refresh
      const [items, stats] = await Promise.all([
        getTags(tagModalKbId),
        getTagStats(tagModalKbId),
      ]);
      setTagList(items);
      setTagStats(stats);
    } catch {
      // handled
    }
  };

  const handleDeleteTag = async (tagId: string) => {
    if (!tagModalKbId) return;
    try {
      await deleteTagApi(tagModalKbId, tagId);
      message.success('标签已删除');
      setTagList((prev) => prev.filter((t) => t.id !== tagId));
      setTagStats((prev) => prev.filter((t) => t.id !== tagId));
    } catch {
      // handled
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20,
        }}
      >
        <Title level={3} style={{ margin: 0, fontFamily: 'var(--f-display)' }}>
          知识库
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          创建知识库
        </Button>
      </div>

      {/* 搜索 */}
      <Input
        allowClear
        size="large"
        prefix={<SearchOutlined style={{ color: 'var(--ink-3)' }} />}
        placeholder="搜索知识库…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 24, maxWidth: 480 }}
      />

      {loading ? (
        <Spin style={{ display: 'block', padding: 80 }} />
      ) : list.length === 0 ? (
        <Empty description="还没有知识库">
          <Button type="primary" onClick={() => setModalOpen(true)}>
            创建第一个知识库
          </Button>
        </Empty>
      ) : filteredList.length === 0 ? (
        <Empty description={`没有匹配「${search}」的知识库`} />
      ) : (
        <Row gutter={[20, 20]}>
          {filteredList.map((kb: KnowledgeBaseItem, i: number) => (
            <Col xs={24} md={12} xl={8} key={kb.id}>
              <FadeIn delay={Math.min(i * 0.06, 0.4)} style={{ height: '100%' }}>
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
                  onGraph={(id) => navigate(`/kb/${id}/graph`)}
                  onDelete={(id) => handleDelete(id)}
                  onTags={(id) => openTagManager(id, kb.name)}
                />
              </FadeIn>
            </Col>
          ))}
        </Row>
      )}

      {/* ── Create KB Modal ── */}
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

      {/* ── Tag Management Modal ── */}
      <Modal
        title={
          <Space>
            <TagOutlined />
            <span>标签管理 — {tagModalKbName}</span>
          </Space>
        }
        open={!!tagModalKbId}
        onCancel={() => setTagModalKbId(null)}
        footer={null}
        width={520}
        destroyOnClose
      >
        {tagLoading ? (
          <Spin style={{ display: 'block', padding: 40 }} />
        ) : (
          <div>
            {/* Create tag */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <ColorPicker
                value={newTagColor}
                onChange={(_, hex) => setNewTagColor(hex)}
                size="small"
              />
              <Input
                placeholder="新标签名称"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                onPressEnter={handleCreateTag}
                maxLength={20}
                style={{ flex: 1 }}
              />
              <Button
                type="primary"
                size="small"
                onClick={handleCreateTag}
                disabled={!newTagName.trim()}
              >
                创建
              </Button>
            </div>

            {/* Tag stats list */}
            {tagStats.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无标签，创建第一个吧"
              />
            ) : (
              <List
                size="small"
                dataSource={tagStats}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Popconfirm
                        key="del"
                        title="删除此标签？"
                        onConfirm={() => handleDeleteTag(item.id)}
                        okText="删除"
                        cancelText="取消"
                      >
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                        />
                      </Popconfirm>,
                    ]}
                  >
                    <Space>
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          background: item.color,
                          display: 'inline-block',
                        }}
                      />
                      <Text>{item.name}</Text>
                      <Tag>{item.document_count} 篇文档</Tag>
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeBase;
