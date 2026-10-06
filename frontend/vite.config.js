import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // ngrok 으로 로컬 서버를 외부에 공개할 때 쓰는 도메인 (그 외 호스트는 Vite 가 차단한다)
    allowedHosts: ['reconvene-luridness-curdle.ngrok-free.dev'],
    // 브라우저는 항상 이 서버(5173)로만 요청하고, /api 요청은 로컬 백엔드(8080)로 전달한다
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        configure: (proxy) => {
          // Origin 이 ngrok 도메인인 요청을 백엔드 CORS 가 거절하지 않도록,
          // 같은 서버를 거쳐 온 요청은 Origin 헤더를 떼고 보낸다
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.removeHeader('origin')
          })
        },
      },
    },
  },
})
