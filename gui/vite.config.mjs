import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { playwright } from "@vitest/browser-playwright";
import { defineConfig } from "vite";
import { recordRuntime, testRunDir } from "./testArtifacts.cjs";

if (process.env.VITEST) recordRuntime("node");

export default defineConfig({
  resolve: {
    alias: {
      "@core": fileURLToPath(new URL("./src/core", import.meta.url)),
      "@shell": fileURLToPath(new URL("./src/shell", import.meta.url)),
    },
  },
  plugins: [react()],
  test: {
    exclude: ["tests/e2e/**", "tests/demo/**", "node_modules/**", "dist/**"],
    projects: [
      {
        extends: true,
        test: { name: "logic", include: ["src/**/*.test.ts"], environment: "node" },
      },
      {
        extends: true,
        test: {
          name: "component",
          include: ["src/**/*.test.tsx"],
          exclude: ["src/**/*.browser.test.tsx"],
          environment: "jsdom",
          setupFiles: ["./tests/componentSetup.ts"],
        },
      },
      {
        extends: true,
        test: {
          name: "interaction",
          include: ["src/**/*.browser.test.tsx"],
          setupFiles: ["./tests/componentSetup.ts"],
          browser: {
            enabled: true,
            headless: true,
            provider: playwright({
              launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH },
            }),
            instances: [{ browser: "chromium" }],
          },
        },
      },
    ],
    coverage: {
      provider: "v8",
      reportsDirectory: `${testRunDir}/node/coverage/unit`,
      reporter: ["html", "text-summary", "lcovonly"],
      all: true,
      include: ["src/**/*.ts", "src/**/*.tsx"],
      thresholds: {
        statements: 85,
        branches: 80,
        functions: 83,
        lines: 87,
        "src/core/**": { lines: 95 },
        "src/shell/data/**": { lines: 95 },
        "src/shell/infra/**": { lines: 96 },
        "src/shell/state/**": { lines: 64 },
        "src/shell/ui/**": { lines: 85 },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
