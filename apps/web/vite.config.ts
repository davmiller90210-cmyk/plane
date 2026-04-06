import path from "node:path";
import * as dotenv from "dotenv";
import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

dotenv.config({ path: path.resolve(__dirname, ".env") });

// Same-origin embed on app.* (e.g. nginx proxies /_konnecct/plane/ → Plane; must not use "/" or Twenty serves /assets).
const rawBase = process.env.VITE_BASE_PATH?.trim() || "/";
const base =
  rawBase === "/" ? "/" : rawBase.endsWith("/") ? rawBase : `${rawBase}/`;

// Expose only vars starting with VITE_
const viteEnv = Object.keys(process.env)
  .filter((k) => k.startsWith("VITE_"))
  .reduce<Record<string, string>>((a, k) => {
    a[k] = process.env[k] ?? "";
    return a;
  }, {});

export default defineConfig(({ command }) => ({
  base,
  // Bundle for the SSR pass that generates SPA index.html (Node ESM cannot load file-type as CJS named exports).
  ssr: {
    noExternal: ["file-type"],
  },
  define: {
    "process.env": JSON.stringify(viteEnv),
  },
  build: {
    assetsInlineLimit: 0,
  },
  server: {
    host: "127.0.0.1",
    origin: command === "serve" ? "http://127.0.0.1:3000" : undefined,
    port: 3000,
  },
  plugins: [reactRouter(), tsconfigPaths({ projects: [path.resolve(__dirname, "tsconfig.json")] })],
  resolve: {
    alias: {
      // Next.js compatibility shims used within web
      "next/link": path.resolve(__dirname, "app/compat/next/link.tsx"),
      "next/navigation": path.resolve(__dirname, "app/compat/next/navigation.ts"),
      "next/script": path.resolve(__dirname, "app/compat/next/script.tsx"),
    },
    dedupe: ["react", "react-dom", "@headlessui/react"],
  },
  // No SSR-specific overrides needed; alias resolves to ESM build
}));
