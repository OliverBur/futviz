import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Un solo archivo autoejecutable (IIFE) y no una app con index.html: el sitio es
// estático y las vistas se cargan con <script src> (ver `web/section_views.py`),
// así que el bundle tiene que funcionar igual abierto con doble clic (file://) que
// servido. Sale a `build/`; `web/build.py` lo copia a `dist/react/` (que borra y
// regenera entero en cada corrida).
export default defineConfig({
  plugins: [react()],
  // React y MUI leen process.env.NODE_ENV; en el navegador no existe.
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "build",
    emptyOutDir: true,
    sourcemap: false,
    lib: {
      entry: "src/main.jsx",
      name: "FutvizReact",
      formats: ["iife"],
      fileName: () => "futviz-react.js",
    },
  },
});
