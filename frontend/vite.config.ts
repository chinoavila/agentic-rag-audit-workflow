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
    // Vite 5.4+ rechaza por default cualquier Host header que no sea localhost/127.0.0.1
    // ("Blocked request. This host is not allowed"). Server accesible en la red local para
    // que usuarios de prueba lo abran desde otra máquina (por IP del host, no solo
    // localhost) -- sin esto, la app ni siquiera carga para ellos (pantalla en blanco con
    // ese mensaje, antes de que corra una sola línea de React).
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
