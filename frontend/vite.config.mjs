import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, loadEnv, transformWithOxc } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const hotReloadDisabled = process.env.CI === "true" || process.env.DISABLE_HOT_RELOAD === "true";

// CRA parity: JSX lives in .js files (App.js, index.js). Vite's transform
// is configured explicitly so the frontend builds without platform-specific plugins.
// CRA parity: JSX lives in .js files (App.js, index.js). Vite 8's native transform picks
// the language from the extension and the visual-edits plugin only tags .jsx/.tsx, so .js
// under src/ is handled here: stamp the x-* visual-edit metadata first (dev only, same
// babel plugin the package runs on .jsx), then compile the JSX away with oxc.
function jsxInJs() {
  return {
    name: "cra-jsx-in-js",
    enforce: "pre",
    transform(code, id) {
      const [file] = id.split("?");
      if (!/\/src\/.*\.js$/.test(file) || file.includes("/node_modules/")) return null;
      return transformWithOxc(code, file, { lang: "jsx", jsx: { runtime: "automatic" } });
    },
  };
}

// Pod inotify quota is node-shared and routinely exhausted; native fs.watch EMFILEs at
// boot. Polling is the load-bearing default (set before Vite evaluates the config).
if (!hotReloadDisabled) {
  process.env.CHOKIDAR_USEPOLLING = "true";
}

// https://vite.dev/config/
export default defineConfig(async ({ mode, command }) => {
  const env = loadEnv(mode, __dirname, ["REACT_APP_", "VITE_"]);
  return {
    base: process.env.VITE_GITHUB_PAGES === "true" ? "/Dns-energy.ro/" : "/",
    plugins: [
      // Visual-edit tagging is dev-server-only, matching the package's own apply: serve.
      jsxInJs(),
      react(),
      tailwindcss(),
      // No isServe guard: this factory takes no ConfigEnv arg, so build purity here rests
      // on the package's own `apply: "serve"`.
    ],
    // CRA parity: REACT_APP_* stays the frontend env convention (frontend/.env).
    envPrefix: ["VITE_", "REACT_APP_"],
    // CRA parity: app code reads `process.env.REACT_APP_*`; Vite has no process.env in the
    // browser, so each REACT_APP_ key is inlined as a compile-time constant.
    define: Object.fromEntries(
      Object.entries(env)
        .filter(([key]) => key.startsWith("REACT_APP_"))
        .map(([key, value]) => [`process.env.${key}`, JSON.stringify(value)]),
    ),
    resolve: {
      alias: [{ find: "@", replacement: path.resolve(__dirname, "./src") }],
    },
    // Every shipped dep, pre-bundled up front. Vite discovers deps lazily, so the first
    // import outside the initial graph would trigger a re-optimize + reload mid-session.
    optimizeDeps: {
      // The dependency scanner runs without user plugins, so it must be told itself that
      // src/**/*.js carries JSX (otherwise it fails the scan and skips pre-bundling).
      rolldownOptions: { moduleTypes: { ".js": "jsx" } },
      include: [
        "@hookform/resolvers",
        "@hookform/resolvers/zod",
        "@radix-ui/react-accordion",
        "@radix-ui/react-alert-dialog",
        "@radix-ui/react-aspect-ratio",
        "@radix-ui/react-avatar",
        "@radix-ui/react-checkbox",
        "@radix-ui/react-collapsible",
        "@radix-ui/react-context-menu",
        "@radix-ui/react-dialog",
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-hover-card",
        "@radix-ui/react-label",
        "@radix-ui/react-menubar",
        "@radix-ui/react-navigation-menu",
        "@radix-ui/react-popover",
        "@radix-ui/react-progress",
        "@radix-ui/react-radio-group",
        "@radix-ui/react-scroll-area",
        "@radix-ui/react-select",
        "@radix-ui/react-separator",
        "@radix-ui/react-slider",
        "@radix-ui/react-slot",
        "@radix-ui/react-switch",
        "@radix-ui/react-tabs",
        "@radix-ui/react-toast",
        "@radix-ui/react-toggle",
        "@radix-ui/react-toggle-group",
        "@radix-ui/react-tooltip",
        "@tanstack/react-query",
        "axios",
        "class-variance-authority",
        "clsx",
        "cmdk",
        "date-fns",
        "date-fns/locale",
        "dayjs",
        "embla-carousel-react",
        "framer-motion",
        "input-otp",
        "lodash",
        "lodash/debounce",
        "lucide-react",
        "next-themes",
        "prop-types",
        "react",
        "react-day-picker",
        "react-dom/client",
        "react-hook-form",
        "react-is",
        "react-resizable-panels",
        "react-router",
        "react-router-dom",
        "recharts",
        "sonner",
        "swr",
        "tailwind-merge",
        "uuid",
        "vaul",
        "zod",
      ],
    },
    // CRA parity: production bundle lands in build/, not dist/.
    build: { outDir: "build" },
    server: {
      host: true,
      port: 3000,
      allowedHosts: true,
      // Preview probe + /edit-file are cross-origin from the Emergent tab; Vite defaults to localhost-only CORS.
      cors: true,
      // No hmr.clientPort override: Vite infers the WS target from window.location, which
      // is correct on both localhost:3000 (smoke) and the https/:443 preview proxy.
      // Build-error rendering: emergent-overlay when it loaded, else Vite's own overlay.
      hmr: hotReloadDisabled ? false : { overlay: true },
      watch: hotReloadDisabled ? null : { usePolling: true, interval: 300 },
    },
  };
});
