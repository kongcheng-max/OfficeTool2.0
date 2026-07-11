import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp, Spin } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/AppLayout';
import Login from './pages/Login';
import { useAuthStore } from './stores/authStore';

// W10.4: 页面级代码分割 — 按路由懒加载，减小首屏体积
const Dashboard = lazy(() => import('./pages/Dashboard'));
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase/index'));
const Documents = lazy(() => import('./pages/Documents/index'));
const Chat = lazy(() => import('./pages/Chat/index'));
const GraphPage = lazy(() => import('./pages/Graph/index'));
const AdminPage = lazy(() => import('./pages/Admin/index'));  // W11.9

/** Suspense 加载中占位 */
const PageLoader: React.FC = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '40vh',
  }}>
    <Spin size="large" tip="加载中…" />
  </div>
);

/** Route guard: redirect to /login if no token */
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = useAuthStore((s) => s.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1677FF',
          borderRadius: 6,
        },
      }}
    >
      <AntApp>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route path="/" element={<Dashboard />} />
              <Route path="/kb/manage" element={<KnowledgeBase />} />
              <Route path="/kb/:id/documents" element={<Documents />} />
              <Route path="/kb/:id/chat" element={<Chat />} />
              <Route path="/kb/:id/graph" element={<GraphPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AntApp>
    </ConfigProvider>
  );
};

export default App;
