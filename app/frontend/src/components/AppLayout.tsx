import React from 'react';
import { Layout, Menu, Avatar, Dropdown, Button, Breadcrumb } from 'antd';
import {
  DashboardOutlined,
  MessageOutlined,
  BookOutlined,
  LogoutOutlined,
  UserOutlined,
  HomeOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useKBStore } from '../stores/kbStore';

const { Header, Sider, Content } = Layout;

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '首页' },
    { key: '/kb/manage', icon: <BookOutlined />, label: '知识库' },
  ];

  // Determine selected menu key from path
  const selectedKey = location.pathname.startsWith('/kb/')
    ? '/kb/manage'
    : location.pathname === '/'
      ? '/'
      : '';

  // Breadcrumb generation
  const kbList = useKBStore((s) => s.list);
  const pathParts = location.pathname.split('/').filter(Boolean);
  const breadcrumbItems: { title: React.ReactNode }[] = [
    { title: <Link to="/"><HomeOutlined /> 首页</Link> },
  ];
  if (pathParts[0] === 'kb') {
    breadcrumbItems.push({ title: <Link to="/kb/manage">知识库管理</Link> });
    if (pathParts[1] === 'manage') {
      // already at kb/manage
    } else if (pathParts[1] && pathParts[2]) {
      const kb = kbList.find((k) => k.id === pathParts[1]);
      const kbName = kb?.name || `知识库 #${pathParts[1].slice(0, 8)}`;
      if (pathParts[2] === 'documents') {
        breadcrumbItems.push({ title: <Link to={`/kb/${pathParts[1]}/chat`}>{kbName}</Link> });
        breadcrumbItems.push({ title: '文档管理' });
      } else if (pathParts[2] === 'chat') {
        breadcrumbItems.push({ title: <Link to={`/kb/${pathParts[1]}/documents`}>{kbName}</Link> });
        breadcrumbItems.push({ title: '智能问答' });
      } else if (pathParts[2] === 'graph') {
        breadcrumbItems.push({ title: <Link to={`/kb/${pathParts[1]}/documents`}>{kbName}</Link> });
        breadcrumbItems.push({ title: '知识图谱' });
      }
    }
  }

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        style={{ background: '#001529' }}
        breakpoint="lg"
        collapsedWidth="80"
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 18,
            fontWeight: 700,
            letterSpacing: 2,
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          OfficeTool
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            borderBottom: '1px solid #f0f0f0',
            height: 64,
          }}
        >
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" icon={<Avatar size="small" icon={<UserOutlined />} />}>
              {user?.username || '用户'}
            </Button>
          </Dropdown>
        </Header>

        <Content
          style={{
            margin: 0,
            padding: 24,
            background: '#f5f5f5',
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Breadcrumb
            items={breadcrumbItems}
            style={{ marginBottom: 16 }}
          />
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
