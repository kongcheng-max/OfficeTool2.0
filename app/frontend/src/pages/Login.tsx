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
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 8px 24px rgba(0,0,0,0.15)' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2} style={{ marginBottom: 4 }}>
            OfficeTool
          </Title>
          <Text type="secondary">企业文档智能解析与问答系统</Text>
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

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              {activeTab === 'login' ? '登录' : '注册'}
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Login;
