import React, { useEffect } from 'react';
import { Row, Col, Card, Typography, List, Tag, Spin, Empty } from 'antd';
import {
  BookOutlined,
  FileTextOutlined,
  MessageOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useKBStore } from '../stores/kbStore';
import CountUp from '../components/motion/CountUp';
import { FadeIn } from '../components/motion/FadeIn';

const { Title, Text } = Typography;

interface KpiProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  tint: string;
}

const KpiCard: React.FC<KpiProps> = ({ icon, label, value, tint }) => (
  <Card style={{ height: '100%' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <div
        style={{
          width: 46,
          height: 46,
          borderRadius: 12,
          display: 'grid',
          placeItems: 'center',
          fontSize: 22,
          flex: 'none',
          color: tint,
          background: `color-mix(in srgb, ${tint} 14%, transparent)`,
        }}
      >
        {icon}
      </div>
      <div>
        <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26, lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>
          <CountUp to={value} />
        </div>
        <div style={{ fontSize: 13, color: 'var(--ink-2)' }}>{label}</div>
      </div>
    </div>
  </Card>
);

const Dashboard: React.FC = () => {
  const { list, loading, fetchList } = useKBStore();
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const totalDocs = list.reduce((sum, kb) => sum + (kb.doc_count || kb.document_count || 0), 0);
  const totalQAs = list.reduce((sum, kb) => sum + (kb.qa_count || 0), 0);
  const totalChunks = list.reduce((sum, kb) => sum + (kb.chunk_count || 0), 0);

  return (
    <div style={{ padding: 24, maxWidth: 1160, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0, fontFamily: 'var(--f-display)' }}>
          你好，{user?.username || '欢迎回来'}
        </Title>
        <Text type="secondary">这是你的知识库总览</Text>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} lg={6}>
          <FadeIn delay={0}><KpiCard icon={<BookOutlined />} label="知识库" value={list.length} tint="var(--brand)" /></FadeIn>
        </Col>
        <Col xs={12} lg={6}>
          <FadeIn delay={0.08}><KpiCard icon={<FileTextOutlined />} label="文档" value={totalDocs} tint="var(--success)" /></FadeIn>
        </Col>
        <Col xs={12} lg={6}>
          <FadeIn delay={0.16}><KpiCard icon={<MessageOutlined />} label="问答" value={totalQAs} tint="var(--warning)" /></FadeIn>
        </Col>
        <Col xs={12} lg={6}>
          <FadeIn delay={0.24}><KpiCard icon={<DatabaseOutlined />} label="分块" value={totalChunks} tint="var(--brand)" /></FadeIn>
        </Col>
      </Row>

      <Card title="最近的知识库">
        {loading ? (
          <Spin style={{ display: 'block', padding: 48 }} />
        ) : list.length === 0 ? (
          <Empty description="暂无知识库，去创建一个吧">
            <a onClick={() => navigate('/kb/manage')}>前往知识库管理</a>
          </Empty>
        ) : (
          <List
            dataSource={list.slice(0, 5)}
            renderItem={(kb) => (
              <List.Item
                extra={
                  <Tag color="blue" style={{ cursor: 'pointer' }} onClick={() => navigate(`/kb/${kb.id}/chat`)}>
                    进入问答
                  </Tag>
                }
              >
                <List.Item.Meta
                  avatar={
                    <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--halo)', color: 'var(--brand)', display: 'grid', placeItems: 'center', fontSize: 18 }}>
                      <DatabaseOutlined />
                    </div>
                  }
                  title={<a onClick={() => navigate(`/kb/${kb.id}/chat`)}>{kb.name}</a>}
                  description={
                    <Text type="secondary">
                      {kb.doc_count || kb.document_count || 0} 份文档 · {kb.qa_count || 0} 次问答 · 创建于{' '}
                      {kb.created_at ? new Date(kb.created_at).toLocaleDateString('zh-CN') : '-'}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
};

export default Dashboard;
