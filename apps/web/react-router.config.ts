import type { Config } from "@react-router/dev/config";

const raw = process.env.VITE_BASE_PATH?.trim() || "/";
const basename =
  raw === "/" || raw === "" ? undefined : raw.replace(/\/$/, "") || undefined;

export default {
  appDirectory: "app",
  // Web runs as a client-side app; build a static client bundle only
  ssr: false,
  basename,
} satisfies Config;
