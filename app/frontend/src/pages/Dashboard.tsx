import React, { useEffect } from 'react';
import { Row, Col, Card, Statistic, Typography, List, Tag, Spin, Empty } from 'antd';
import {
  BookOutlined,
  FileTextOutlined,
  MessageOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useKBStore } from '../stores/kbStore';

const { Title, Text } = Typography;

const Dashboard: React.FC = () => {
  const { list, loading, fetchList } = useKBStore();
  const navigate = useNavigate();

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const totalDocs = list.reduce((sum, kb) => sum + (kb.doc_count || kb.document_count || 0), 0);
  const totalQAs = list.reduce((sum, kb) => sum + (kb.qa_count || 0), 0);
  const totalChunks = list.reduce((sum, kb) => sum + (kb.chunk_count || 0), 0);

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        首页概览
      </Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="知识库总数"
              value={list.length}
              prefix={<BookOutlined />}
              valueStyle={{ color: '#1677FF' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="文档总数"
              value={totalDocs}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#52C41A' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="问答总数"
              value={totalQAs}
              prefix={<MessageOutlined />}
              valueStyle={{ color: '#FAAD14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总块数"
              value={totalChunks}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#722ED1' }}
            />
          </Card>
        </Col>
      </Row>

      <Card title="我的知识库" style={{ marginBottom: 24 }}>
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
                  <Tag color="blue" style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/kb/${kb.id}/chat`)}>
                    进入问答
                  </Tag>
                }
              >
                <List.Item.Meta
                  title={
                    <a onClick={() => navigate(`/kb/${kb.id}/chat`)}>{kb.name}</a>
                  }
                  description={
                    <Text type="secondary">
                      📄 {kb.doc_count || kb.document_count || 0} 份文档 · 💬 {kb.qa_count || 0} 次问答 ·{' '}
                      创建于 {kb.created_at ? new Date(kb.created_at).toLocaleDateString('zh-CN') : '-'}
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
