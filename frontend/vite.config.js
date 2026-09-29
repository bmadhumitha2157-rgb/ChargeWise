import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Dev only: proxies /api to the local backend. In production the app uses VITE_API_URL instead.
export default defineConfig({ plugins: [react()], server: { port: 5173, proxy: { "/api": process.env.VITE_DEV_PROXY || "http://localhost:8000" } } });
