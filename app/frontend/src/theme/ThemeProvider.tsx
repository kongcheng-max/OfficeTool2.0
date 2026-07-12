import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ConfigProvider, App as AntApp, theme as antdTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { antdToken, antdComponents, type ThemeMode } from './tokens';

interface ThemeCtx {
  mode: ThemeMode;
  toggle: () => void;
  setMode: (m: ThemeMode) => void;
}

const Ctx = createContext<ThemeCtx>({ mode: 'light', toggle: () => {}, setMode: () => {} });

/** 读取用户主题偏好：localStorage → 系统偏好 → light */
function initialMode(): ThemeMode {
  const saved = localStorage.getItem('officetool_theme');
  if (saved === 'light' || saved === 'dark') return saved;
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  return 'light';
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<ThemeMode>(initialMode);

  // 同步到 <html data-theme> 供 CSS 变量切换
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode);
    localStorage.setItem('officetool_theme', mode);
  }, [mode]);

  const ctx = useMemo<ThemeCtx>(
    () => ({ mode, setMode, toggle: () => setMode((m) => (m === 'light' ? 'dark' : 'light')) }),
    [mode],
  );

  return (
    <Ctx.Provider value={ctx}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
          token: antdToken(mode),
          components: antdComponents(mode),
        }}
      >
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </Ctx.Provider>
  );
};

export const useTheme = () => useContext(Ctx);
