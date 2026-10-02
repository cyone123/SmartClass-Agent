import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // rewrite: path => path.replace(/^\/api/, '')
      },
      '/savefile': {
        target: 'http://8.155.29.72',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/savefile/, '')
      },
      '/web-apps': {
        target: 'http://8.155.29.72',
        changeOrigin: true
      },
      '/sdkjs': {
        target: 'http://8.155.29.72',
        changeOrigin: true
      },
      '/coauthoring': {
        target: 'http://8.155.29.72',
        changeOrigin: true,
        ws: true
      },
      '/cache': {
        target: 'http://8.155.29.72',
        changeOrigin: true
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
})
