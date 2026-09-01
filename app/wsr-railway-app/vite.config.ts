import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { cameraTracks } from './vite-plugin-camera-tracks'
import { localMedia } from './vite-plugin-local-media'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    // The annotator writes camera_tracks.json, which a browser cannot do
    // alone. Serving that endpoint from the dev server keeps it one app on
    // one port rather than a second server to start and to miss when it
    // stops.
    plugins: [react(), cameraTracks(), localMedia()],
    base: env.BASE_PATH || '/',
    build: {
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return
            if (id.includes('leaflet')) return 'leaflet'
            if (/[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) return 'react'
          },
        },
      },
    },
  }
})
