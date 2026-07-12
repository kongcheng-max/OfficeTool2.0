import React, { useEffect, useState, useCallback } from 'react';
import { Table, Typography, Select, Button, Popconfirm, Space, Tag, Tabs, App } from 'antd';
import { UserDeleteOutlined, AuditOutlined, TeamOutlined } from '@ant-design/icons';
import client from '../../api/client';

const { Title, Text } = Typography;

interface UserItem {
  id: string; username: string; email: string; role: string;
  is_active: boolean; created_at: string;
}
interface AuditItem {
  id: number; username: string; action: string; ip_address: string;
  success: boolean; status_code: number; created_at: string;
}

const Admin: React.FC = () => {
  const { message, modal } = App.useApp();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [userTotal, setUserTotal] = useState(0);
  const [userPage, setUserPage] = useState(1);
  const [userLoading, setUserLoading] = useState(false);

  const [logs, setLogs] = useState<AuditItem[]>([]);
  const [logTotal, setLogTotal] = useState(0);
  const [logPage, setLogPage] = useState(1);
  const [logLoading, setLogLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    setUserLoading(true);
    try {
      // client 响应拦截器已解包为 {items,total,...}，此处按运行时形状读取
      const res: any = await client.get('/admin/users', { params: { page: userPage, page_size: 20 } });
      setUsers(res.items || []);
      setUserTotal(res.total || 0);
    } catch { /* axios interceptor handles error toast */ }
    setUserLoading(false);
  }, [userPage]);

  const fetchLogs = useCallback(async () => {
    setLogLoading(true);
    try {
      const res: any = await client.get('/admin/audit-logs', { params: { page: logPage, page_size: 50 } });
      setLogs(res.items || []);
      setLogTotal(res.total || 0);
    } catch { /* axios interceptor handles error toast */ }
    setLogLoading(false);
  }, [logPage]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);
  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await client.put(`/admin/users/${userId}/role`, null, { params: { role: newRole } });
      message.success('角色已更新');
      fetchUsers();
    } catch (e: any) {
      message.error(`更新失败: ${e?.message || '未知错误'}`);
    }
  };

  const handleDeleteUser = async (userId: string, username: string) => {
    try {
      await client.delete(`/admin/users/${userId}`);
      message.success(`用户 ${username} 已删除`);
      fetchUsers();
    } catch (e: any) {
      message.error(`删除失败: ${e?.message || '未知错误'}`);
    }
  };

  const userColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email', render: (v: string) => v || '-' },
    {
      title: '角色', dataIndex: 'role', key: 'role',
      render: (role: string, record: UserItem) => (
        <Select
          value={role}
          size="small"
          style={{ width: 100 }}
          onChange={(val) => handleRoleChange(record.id, val)}
          options={[
            { value: 'admin', label: '管理员' },
            { value: 'editor', label: '编辑者' },
            { value: 'viewer', label: '观察者' },
          ]}
        />
      ),
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active',
      render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '活跃' : '禁用'}</Tag>,
    },
    {
      title: '注册时间', dataIndex: 'created_at', key: 'created_at',
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: UserItem) => (
        <Popconfirm
          title={`确定删除用户 ${record.username}？`}
          onConfirm={() => handleDeleteUser(record.id, record.username)}
          okText="删除" cancelText="取消"
        >
          <Button type="text" danger icon={<UserDeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  const logColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
    { title: '操作', dataIndex: 'action', key: 'action', width: 140 },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip', width: 140, render: (v: string) => v || '-' },
    {
      title: '结果', dataIndex: 'success', key: 'success', width: 70,
      render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '成功' : '失败'}</Tag>,
    },
    {
      title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 70,
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 24, fontFamily: 'var(--f-display)' }}>管理后台</Title>

      <Tabs
        items={[
          {
            key: 'users',
            label: <span><TeamOutlined /> 用户管理</span>,
            children: (
              <Table
                columns={userColumns}
                dataSource={users}
                rowKey="id"
                loading={userLoading}
                pagination={{
                  current: userPage, total: userTotal, pageSize: 20,
                  showTotal: (t) => `共 ${t} 个用户`,
                  onChange: (p) => setUserPage(p),
                }}
                size="middle"
              />
            ),
          },
          {
            key: 'logs',
            label: <span><AuditOutlined /> 审计日志</span>,
            children: (
              <Table
                columns={logColumns}
                dataSource={logs}
                rowKey="id"
                loading={logLoading}
                pagination={{
                  current: logPage, total: logTotal, pageSize: 50,
                  showTotal: (t) => `共 ${t} 条日志`,
                  onChange: (p) => setLogPage(p),
                }}
                size="small"
              />
            ),
          },
        ]}
      />
    </div>
  );
};

export default Admin;
