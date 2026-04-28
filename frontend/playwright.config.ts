

export default {
  testDir: "./tests/e2e",
  timeout: 3 * 1000,
  expect: {
    timeout: 3 * 1000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    viewport: { width: 1920, height: 1080 },
    video: {
      mode: 'on',
      size: { width: 1920, height: 1080 },
    },
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
    timeout: 10 * 1000,
    env: {
      VITE_API_BASE_URL: "http://localhost:8000",
    },
  },
};
