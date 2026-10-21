import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    host: "127.0.0.1", port: 5173, allowedHosts: true,
    // used inside a GitHub Codespace: /api/* -> the FastAPI backend (HTTP and WebSocket)
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true, ws: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
  build: { chunkSizeWarningLimit: 900 },
});
