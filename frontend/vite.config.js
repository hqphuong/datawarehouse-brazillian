import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const workspaceDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, workspaceDir, '')
  const host = env.BACKEND_HOST || 'localhost'
  const target = new URL(/^https?:\/\//i.test(host) ? host : `http://${host}`)
  target.port = env.BACKEND_PORT || target.port || '8000'
  target.pathname = ''
  target.search = ''
  target.hash = ''
  const proxy = { '/api': { target: target.origin, changeOrigin: true } }

  return {
    envDir: workspaceDir,
    plugins: [react()],
    server: { proxy },
    preview: { proxy },
  }
})
