import React, { useEffect, useState } from 'react';
import { Avatar, Dropdown, Drawer, Grid, Tooltip, Empty } from 'antd';
import {
  HomeOutlined,
  DatabaseOutlined,
  MessageOutlined,
  DeploymentUnitOutlined,
  FileTextOutlined,
  AuditOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuOutlined,
  BulbOutlined,
  BulbFilled,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useKBStore } from '../stores/kbStore';
import { useTheme } from '../theme/ThemeProvider';

const { useBreakpoint } = Grid;

interface RailItem {
  key: string;
  path: string;
  icon: React.ReactNode;
  label: string;
  match: (p: string) => boolean;
}

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { list: kbList, fetchList } = useKBStore();
  const { mode, toggle } = useTheme();
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [asideCollapsed, setAsideCollapsed] = useState(false);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const path = location.pathname;
  const kbMatch = path.match(/^\/kb\/([^/]+)\/(documents|chat|graph)/);
  const kbId = kbMatch?.[1];
  const currentKB = kbList.find((k) => k.id === kbId);

  // ── 图标栏：全局模块 ──────────────────────────────────
  const railItems: RailItem[] = [
    { key: 'home', path: '/', icon: <HomeOutlined />, label: '首页', match: (p) => p === '/' },
    { key: 'kb', path: '/kb/manage', icon: <DatabaseOutlined />, label: '知识库', match: (p) => p.startsWith('/kb') },
    ...(user?.role === 'admin'
      ? [{ key: 'admin', path: '/admin', icon: <AuditOutlined />, label: '管理后台', match: (p: string) => p.startsWith('/admin') }]
      : []),
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems = [
    { key: 'name', label: user?.username || '用户', disabled: true },
    { type: 'divider' as const },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  // ── 面包屑 ────────────────────────────────────────────
  const crumbs: { label: string; to?: string }[] = [{ label: '首页', to: '/' }];
  if (path.startsWith('/kb')) {
    crumbs.push({ label: '知识库', to: '/kb/manage' });
    if (kbId && currentKB) {
      crumbs.push({ label: currentKB.name, to: `/kb/${kbId}/chat` });
      const section = kbMatch?.[2];
      crumbs.push({ label: section === 'documents' ? '文档管理' : section === 'graph' ? '知识图谱' : '智能问答' });
    }
  } else if (path.startsWith('/admin')) {
    crumbs.push({ label: '管理后台' });
  }

  // ── 二级面板内容 ──────────────────────────────────────
  const kbSections = kbId
    ? [
        { key: 'chat', label: '智能问答', icon: <MessageOutlined />, path: `/kb/${kbId}/chat` },
        { key: 'documents', label: '文档管理', icon: <FileTextOutlined />, path: `/kb/${kbId}/documents` },
        { key: 'graph', label: '知识图谱', icon: <DeploymentUnitOutlined />, path: `/kb/${kbId}/graph` },
      ]
    : [];

  const renderAside = () => (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--paper)' }}>
      {kbId && currentKB ? (
        <>
          <button
            onClick={() => navigate('/kb/manage')}
            style={asideBackBtn}
          >
            <RightOutlined style={{ fontSize: 11, transform: 'rotate(180deg)' }} /> 返回全部知识库
          </button>
          <div style={asideHead}>
            <span className="ot-mark" style={{ width: 30, height: 30, borderRadius: 9 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 15, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {currentKB.name}
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                {(currentKB.doc_count ?? currentKB.document_count ?? 0)} 文档
              </div>
            </div>
          </div>
          <div style={{ padding: '4px 10px' }}>
            {kbSections.map((s) => {
              const active = path === s.path;
              return (
                <div key={s.key} onClick={() => navigate(s.path)} style={asideItem(active)}>
                  <span style={{ fontSize: 16 }}>{s.icon}</span>
                  {s.label}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <>
          <div style={asideHead}>
            <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 15, color: 'var(--ink)' }}>
              知识库
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '2px 10px' }}>
            {kbList.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库" style={{ marginTop: 40 }} />
            ) : (
              kbList.map((kb) => {
                const active = kbId === kb.id;
                return (
                  <div key={kb.id} onClick={() => navigate(`/kb/${kb.id}/chat`)} style={asideItem(active)}>
                    <DatabaseOutlined style={{ fontSize: 15, color: active ? 'var(--brand)' : 'var(--ink-3)' }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{kb.name}</span>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );

  const rail = (
    <nav style={railStyle} aria-label="主导航">
      <span className="ot-mark" style={{ width: 36, height: 36, borderRadius: 10, marginBottom: 14 }} />
      {railItems.map((it) => {
        const active = it.match(path);
        return (
          <Tooltip key={it.key} title={it.label} placement="right">
            <div onClick={() => navigate(it.path)} style={railIco(active)} aria-label={it.label}>
              {it.icon}
              {active && <span style={railActiveBar} />}
            </div>
          </Tooltip>
        );
      })}
      <div style={{ flex: 1 }} />
      <Tooltip title={mode === 'light' ? '暗色模式' : '亮色模式'} placement="right">
        <div onClick={toggle} style={railIco(false)} aria-label="切换主题">
          {mode === 'light' ? <BulbOutlined /> : <BulbFilled />}
        </div>
      </Tooltip>
      <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
        <Avatar
          size={34}
          style={{ cursor: 'pointer', background: 'linear-gradient(140deg, var(--success), var(--brand))', marginTop: 4 }}
        >
          {(user?.username || 'U').slice(0, 1).toUpperCase()}
        </Avatar>
      </Dropdown>
    </nav>
  );

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--body)', color: 'var(--ink)' }}>
      {/* 图标栏 —— 桌面常驻 */}
      {!isMobile && rail}

      {/* 二级面板 —— 桌面可折叠 */}
      {!isMobile && !asideCollapsed && (
        <aside style={{ width: 260, flexShrink: 0, borderRight: '1px solid var(--divider)' }}>
          {renderAside()}
        </aside>
      )}

      {/* 移动端抽屉 */}
      <Drawer
        placement="left"
        open={isMobile && drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={300}
        styles={{ body: { padding: 0, display: 'flex' } }}
        closable={false}
      >
        {rail}
        <div style={{ flex: 1 }}>{renderAside()}</div>
      </Drawer>

      {/* 主区 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={topbarStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            {isMobile ? (
              <div onClick={() => setDrawerOpen(true)} style={iconBtn}><MenuOutlined /></div>
            ) : (
              <div onClick={() => setAsideCollapsed((c) => !c)} style={iconBtn} title={asideCollapsed ? '展开侧栏' : '收起侧栏'}>
                {asideCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--ink-2)', overflow: 'hidden' }}>
              {crumbs.map((c, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span style={{ color: 'var(--ink-3)' }}>/</span>}
                  {c.to ? (
                    <span onClick={() => navigate(c.to!)} style={{ cursor: 'pointer', whiteSpace: 'nowrap' }}>{c.label}</span>
                  ) : (
                    <b style={{ color: 'var(--ink)', fontWeight: 600, whiteSpace: 'nowrap' }}>{c.label}</b>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {isMobile && (
              <div onClick={toggle} style={iconBtn} title="切换主题">
                {mode === 'light' ? <BulbOutlined /> : <BulbFilled />}
              </div>
            )}
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 8px', borderRadius: 9 }}>
                <Avatar size={28} icon={<UserOutlined />} style={{ background: 'var(--brand)' }} />
                {!isMobile && <span style={{ fontSize: 13, color: 'var(--ink)' }}>{user?.username || '用户'}</span>}
              </div>
            </Dropdown>
          </div>
        </header>

        <main style={{ flex: 1, overflow: 'auto', background: 'var(--body)' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};

// ── 样式 ────────────────────────────────────────────────
const railStyle: React.CSSProperties = {
  width: 68,
  flexShrink: 0,
  background: 'var(--nav)',
  borderRight: '1px solid var(--divider)',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  padding: '16px 0',
  gap: 4,
};

const railIco = (active: boolean): React.CSSProperties => ({
  position: 'relative',
  width: 44,
  height: 44,
  borderRadius: 11,
  display: 'grid',
  placeItems: 'center',
  cursor: 'pointer',
  fontSize: 20,
  color: active ? 'var(--brand)' : 'var(--ink-3)',
  background: active ? 'var(--active)' : 'transparent',
  transition: 'background .16s ease, color .16s ease',
});

const railActiveBar: React.CSSProperties = {
  position: 'absolute',
  left: -16,
  top: 11,
  bottom: 11,
  width: 3,
  borderRadius: '0 3px 3px 0',
  background: 'var(--brand)',
};

const topbarStyle: React.CSSProperties = {
  height: 56,
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '0 16px',
  background: 'var(--paper)',
  borderBottom: '1px solid var(--divider)',
};

const iconBtn: React.CSSProperties = {
  width: 34,
  height: 34,
  borderRadius: 9,
  display: 'grid',
  placeItems: 'center',
  cursor: 'pointer',
  color: 'var(--ink-2)',
  fontSize: 16,
};

const asideHead: React.CSSProperties = {
  padding: '16px 18px 12px',
  display: 'flex',
  alignItems: 'center',
  gap: 10,
};

const asideBackBtn: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  border: 'none',
  background: 'transparent',
  color: 'var(--ink-2)',
  cursor: 'pointer',
  fontSize: 12.5,
  padding: '14px 18px 0',
  fontFamily: 'inherit',
};

const asideItem = (active: boolean): React.CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '10px 12px',
  borderRadius: 10,
  cursor: 'pointer',
  marginBottom: 2,
  fontSize: 13.5,
  fontWeight: active ? 600 : 500,
  color: active ? 'var(--brand)' : 'var(--ink)',
  background: active ? 'var(--active)' : 'transparent',
  transition: 'background .14s ease',
});

export default AppLayout;
