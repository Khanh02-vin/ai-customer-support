import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy các route API sang backend FastAPI (cùng path như production)
const API_TARGET = "http://localhost:8005";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    port: 5173,
    proxy: {
      "/auth": API_TARGET,
      "/chat": API_TARGET,
      "/kb": API_TARGET,
      "/tickets": API_TARGET,
      "/stats": API_TARGET,
      "/config": API_TARGET,
      "/widget": API_TARGET,
      "/health": API_TARGET,
    },
  },
});
