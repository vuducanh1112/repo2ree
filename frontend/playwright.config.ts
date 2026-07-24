import { defineConfig } from "@playwright/test";

// When E2E_BASE_URL is set, the tests run against an externally provided
// frontend (e.g. the compose image stack on :3000) and no vite dev server is
// started. Default: playwright starts its own dev server on :4173.
const externalBaseURL = process.env.E2E_BASE_URL;

const baseUse = {
  baseURL: externalBaseURL ?? "http://127.0.0.1:4173",
  browserName: "chromium" as const,
  launchOptions: {
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
  },
  viewport: { width: 1920, height: 1080 },
};

export default defineConfig({
  testDir: "./tests",
  // Each test provisions a real workbench container against the single shared
  // backend, so the suite must run serially. `fullyParallel: false` alone only
  // serializes within a file — `workers: 1` is what prevents spec files from
  // racing each other across workers.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  webServer: externalBaseURL
    ? undefined
    : {
        command: "npm run dev -- --host 127.0.0.1 --port 4173",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: true,
        timeout: 10 * 1000,
        env: {
          VITE_API_BASE_URL: "http://localhost:8000",
        },
      },
  projects: [
    {
      // Lean regression tests: no narration, no artificial delays.
      // No video (avoids the ffmpeg dependency + per-test recording cost);
      // a trace is kept only for failures, which is cheap and debuggable.
      name: "e2e",
      testDir: "./tests/e2e",
      // The review specs are their own project (below), so the authoring suite
      // does not also run them.
      testIgnore: ["**/review/**"],
      outputDir: "./test-artifacts/playwright/e2e",
      // Generous per-test budget: with DinD, each workbench builds against a
      // cold (empty) image cache, so a test that builds + runs can need ~60s+.
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
      // The reviewer side of the lifecycle: one spec per review step, each
      // reproducing that step in an isolated namespace and comparing what comes
      // out with the author's recorded evidence. Same lean setup as the e2e
      // project — it is a regression suite, not a recording — but its own
      // project so a reviewer-facing change can be validated on its own, and
      // with a larger budget: a review re-runs work the author already did, on
      // top of doing it once to have something to review.
      name: "review",
      testDir: "./tests/e2e/review",
      outputDir: "./test-artifacts/playwright/review",
      timeout: 420 * 1000,
      expect: { timeout: 15 * 1000 },
      use: {
        ...baseUse,
        video: "off",
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
      },
    },
    {
      // Showcase walkthrough: full narration + always-on video recording.
      // The video is the artifact, so no trace; separate outputDir so its
      // videos never collide with the e2e suite.
      name: "demo",
      testDir: "./tests/demo",
      testIgnore: ["**/code-ocean/**"],
      outputDir: "./test-artifacts/playwright/demo",
      timeout: 300 * 1000,
      expect: { timeout: 10 * 1000 },
      use: {
        ...baseUse,
        video: { mode: "on", size: { width: 1920, height: 1080 } },
        screenshot: "only-on-failure",
      },
    },
    {
      // Long-running, external-image demos. Kept out of `make e2e-demo` so the
      // ordinary narrated demo remains quick and self-contained.
      name: "code-ocean",
      testDir: "./tests/demo/code-ocean",
      outputDir: "./test-artifacts/playwright/code-ocean",
      timeout: 900 * 1000,
      expect: { timeout: 10 * 1000 },
      use: {
        ...baseUse,
        video: { mode: "on", size: { width: 1920, height: 1080 } },
        screenshot: "only-on-failure",
      },
    },
  ],
});
