import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// npm run dev (port 5180): the API and live updates go to the simulator server on 5100
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target: "http://127.0.0.1:5100", ws: true } } },
});
