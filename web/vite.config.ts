import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base './' so the bundle works from the gh-pages project subpath (and file://).
export default defineConfig({
  plugins: [react()],
  base: './',
})
