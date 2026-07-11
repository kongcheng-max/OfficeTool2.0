import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5176,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  // W10.4: 构建优化 — 代码分割 + 体积控制
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心（不会频繁变动，可长期缓存）
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Ant Design + icons（最大的依赖包）
          'vendor-antd': ['antd', '@ant-design/icons'],
        },
      },
    },
    chunkSizeWarningLimit: 600, // KB
    target: 'es2020',
    minify: 'esbuild',
  },
});
