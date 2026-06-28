import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/AppLayout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import KnowledgeBase from './pages/KnowledgeBase/index';
import Documents from './pages/Documents/index';
import Chat from './pages/Chat/index';
import GraphPage from './pages/Graph/index';
import { useAuthStore } from './stores/authStore';

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
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AntApp>
    </ConfigProvider>
  );
};

export default App;
