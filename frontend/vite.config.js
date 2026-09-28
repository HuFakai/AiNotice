import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * 爱通知 AiNotice 前端构建配置
 *
 * - 构建产物输出到 frontend/dist，由 FastAPI 静态托管 + SPA fallback
 * - 开发环境把 /api 代理到本地后端（端口读仓库根目录 .env 的 API_PORT / VITE_API_TARGET）
 */
export default defineConfig(({ mode }) => {
  // 读取仓库根目录的 .env（frontend/ 的上一级），拿到 API_PORT
  const repoRoot = fileURLToPath(new URL('..', import.meta.url))
  const rootEnv = loadEnv(mode, repoRoot, '')
  const localEnv = loadEnv(mode, process.cwd(), '')

  const apiPort = rootEnv.API_PORT || localEnv.API_PORT || '9088'
  const apiHost = rootEnv.API_HOST && rootEnv.API_HOST !== '0.0.0.0' ? rootEnv.API_HOST : '127.0.0.1'
  const target = localEnv.VITE_API_TARGET || rootEnv.VITE_API_TARGET || `http://${apiHost}:${apiPort}`

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        // 注意：必须用 ^/api/ 而不是 '/api'，否则 SPA 路由 /api-keys 会被误代理到后端，
        // 导致刷新 /api-keys 时返回 500 而不是 index.html。
        '^/api/': {
          target,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      // 单页应用，不生成 gzip 之外的额外结构
      assetsDir: 'assets',
      chunkSizeWarningLimit: 1600,
    },
  }
})
