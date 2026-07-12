import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Tabs, Alert, App } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
  const [formError, setFormError] = useState<string | null>(null);
  const { login, register, loading } = useAuthStore();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm();

  const onFinish = async (values: Record<string, string>) => {
    setFormError(null);
    try {
      if (activeTab === 'login') {
        await login(values.username, values.password);
      } else {
        await register(values.username, values.password, values.email);
      }
      message.success(activeTab === 'login' ? '登录成功' : '注册成功');
      navigate('/');
    } catch (e: any) {
      // axios interceptor already shows a toast for API errors;
      // show an inline form error for persistent feedback
      const errMsg = e?.response?.data?.message || e?.message || '操作失败，请重试';
      setFormError(errMsg);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: 'var(--body)' }}>
      {/* 左：品牌展示区 */}
      <div style={brandPanel}>
        <div style={{ position: 'relative', zIndex: 1, maxWidth: 400 }}>
          <span className="ot-mark" style={{ width: 56, height: 56, borderRadius: 16, display: 'inline-block', marginBottom: 22 }} />
          <div style={{ fontFamily: 'var(--f-display)', fontWeight: 700, fontSize: 40, lineHeight: 1.15, color: '#fff', letterSpacing: '-.02em' }}>
            把文档，<br />解析成可信的答案
          </div>
          <div style={{ marginTop: 18, fontSize: 15, color: 'rgba(255,255,255,.82)', lineHeight: 1.7 }}>
            OfficeTool 解析你的合同、制度与研报，用检索增强生成回答问题——每一句结论都连回它的文档来源。
          </div>
          <div style={{ marginTop: 28, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {['智能解析各类文档', 'RAG 精准问答，答案可追溯', '知识图谱可视化'].map((t) => (
              <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'rgba(255,255,255,.9)', fontSize: 14 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'rgba(255,255,255,.7)' }} />
                {t}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 右：表单 */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 24 }}>
        <Card style={{ width: 400, boxShadow: 'var(--sh-lg)', borderRadius: 20 }} styles={{ body: { padding: 32 } }}>
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <Title level={3} style={{ marginBottom: 4, fontFamily: 'var(--f-display)' }}>
              {activeTab === 'login' ? '欢迎回来' : '创建账号'}
            </Title>
            <Text type="secondary">OfficeTool · 企业文档智能解析</Text>
          </div>

          <Tabs
            activeKey={activeTab}
            onChange={(key) => {
              setActiveTab(key as 'login' | 'register');
              form.resetFields();
            }}
            centered
            items={[
              { key: 'login', label: '登录' },
              { key: 'register', label: '注册' },
            ]}
          />

          {formError && (
            <Alert
              type="error"
              message={formError}
              closable
              onClose={() => setFormError(null)}
              style={{ marginBottom: 16 }}
            />
          )}

          <Form form={form} onFinish={onFinish} size="large" autoComplete="off">
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input prefix={<UserOutlined />} placeholder="用户名" />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>

            {activeTab === 'register' && (
              <Form.Item name="email" rules={[{ type: 'email', message: '请输入有效邮箱' }]}>
                <Input prefix={<MailOutlined />} placeholder="邮箱（选填）" />
              </Form.Item>
            )}

            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" loading={loading} block>
                {activeTab === 'login' ? '登录' : '注册'}
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  );
};

const brandPanel: React.CSSProperties = {
  flex: '0 0 46%',
  display: 'flex',
  alignItems: 'center',
  padding: '48px 56px',
  position: 'relative',
  overflow: 'hidden',
  background: 'linear-gradient(150deg, var(--brand-2), var(--brand-strong))',
};

export default Login;
