import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Proxy /api -> backend:8000 en dev: el frontend siempre llama rutas relativas /api/... (nunca
// una URL absoluta), así el build de producción (Dockerfile.frontend, nginx) no necesita
// hornear ninguna URL de backend en el bundle -- ver spec-020.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
