import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, root, "VITE_");
  const apiTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    root,
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.resolve(root, "src") } },
    build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
    server: {
      host: "127.0.0.1",
      allowedHosts: env.VITE_ALLOWED_HOST ? [env.VITE_ALLOWED_HOST] : [],
      proxy: { "/api": { target: apiTarget, changeOrigin: false } },
    },
  };
});
