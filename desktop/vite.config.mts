import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative paths, as the built page is loaded from a file by Electron
export default defineConfig({
  base: "./",
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173, strictPort: true },
  build: { outDir: "dist" },
});
