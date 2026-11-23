import { defineConfig } from "@playwright/test";
import { recordRuntime, testRunDir } from "./testArtifacts.cjs";

recordRuntime("browser");

const externalBaseURL = process.env.E2E_BASE_URL;
const apiBaseURL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
const ownGuiPort = process.env.E2E_GUI_PORT;
const guiPort = ownGuiPort ?? "4173";

const NETWORK_TEST_TIMEOUT = 45 * 60 * 1000;

const baseUse = {
  baseURL: externalBaseURL ?? `http://127.0.0.1:${guiPort}`,
  browserName: "chromium" as const,
  launchOptions: {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  },
  viewport: { width: 1920, height: 1080 },
};

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: process.env.PLAYWRIGHT_JUNIT_OUTPUT_FILE ? [["list"], ["junit"]] : "list",
  webServer: externalBaseURL
    ? undefined
    : {
        command: `npm run dev -- --host 127.0.0.1 --port ${guiPort}${ownGuiPort ? " --strictPort" : ""}`,
        url: `http://127.0.0.1:${guiPort}`,
        reuseExistingServer: ownGuiPort === undefined,
        timeout: 10 * 1000,
        env: {
          VITE_API_BASE_URL: apiBaseURL,
          VITE_BUILD_REVISION: process.env.VITE_BUILD_REVISION ?? "development",
        },
      },
  projects: [
    {
      name: "gui-accessibility-tests",
      testDir: "./tests/gui-accessibility-tests",
      outputDir: `${testRunDir}/browser/tests/gui-accessibility-tests`,
      timeout: 30 * 1000,
      expect: { timeout: 10 * 1000 },
      use: {
        ...baseUse,
        video: "off",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
      },
    },
    {
      name: "gui-screenshot-tests",
      testDir: "./tests/gui-screenshot-tests",
      outputDir: `${testRunDir}/browser/tests/gui-screenshot-tests`,
      timeout: 30 * 1000,
      expect: {
        timeout: 10 * 1000,
        toHaveScreenshot: {
          animations: "disabled",
          caret: "hide",
          maxDiffPixels: 0,
          threshold: 0.05,
        },
      },
      use: {
        ...baseUse,
        video: "off",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
      },
    },
    {
      name: "showcase",
      testDir: "./tests/showcase",
      outputDir: `${testRunDir}/browser/tests/showcase`,
      timeout: NETWORK_TEST_TIMEOUT,
      expect: { timeout: 15 * 1000 },
      use: {
        ...baseUse,
        video: "off",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
      },
    },
    {
      name: "e2e-gui-instant",
      testDir: "./tests/e2e-instant",
      metadata: { runWatch: "instant" },
      outputDir: `${testRunDir}/browser/tests/e2e-gui-instant`,
      timeout: 180 * 1000,
      expect: { timeout: 15 * 1000 },
      use: {
        ...baseUse,
        video: "off",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
      },
    },
    {
      name: "demo-gui",
      testDir: "./tests/showcase",
      testMatch: "python-docker.spec.ts",
      metadata: { narrated: true },
      outputDir: `${testRunDir}/browser/tests/demo-gui`,
      timeout: NETWORK_TEST_TIMEOUT,
      expect: { timeout: 10 * 1000 },
      use: {
        ...baseUse,
        video: { mode: "on", size: { width: 1920, height: 1080 } },
        screenshot: "only-on-failure",
      },
    },
  ],
});
