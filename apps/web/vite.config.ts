import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    modulePreload: {
      polyfill: false,
      resolveDependencies: (_url, deps) => {
        // Exclude heavy 3D and mapping chunks from initial modulepreload
        return deps.filter(
          (dep) =>
            !dep.includes('vendor-three') &&
            !dep.includes('vendor-maplibre') &&
            !dep.includes('TerrainDiorama3D') &&
            !dep.includes('TerrainScene3D') &&
            !dep.includes('PolygonMapDrawer'),
        )
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-three': ['three'],
          'vendor-maplibre': ['maplibre-gl'],
        },
      },
    },
  },
})
