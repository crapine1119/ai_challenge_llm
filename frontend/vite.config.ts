import path from "path";
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const API = env.VITE_API_BASE_URL ?? "http://localhost:8000";
  return {
    plugins: [vue()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") }
    },
    server: { port: 5173 },
    define: { __API_BASE__: JSON.stringify(API) }
  };
});
