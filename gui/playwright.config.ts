import { defineConfig } from "@playwright/test";

// When E2E_BASE_URL is set, the tests run against an externally provided
// GUI (e.g. the compose image stack on :3000) and no vite dev server is
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

// Every `outputDir` below is `../test-artifacts/...`: one artifact root at the
// repo root, shared with the Python suites, rather than a second one under gui/.
// Playwright resolves a relative outputDir against *this file's* directory, not
// the cwd, so these stay correct however the suite is invoked — which is the
// same reason tests/artifacts.ts anchors on __dirname instead of process.cwd().
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
      // Page-level visual regression tests. These render the real routed GUI,
      // but fulfill the HTTP contract from deterministic fixtures so a visual
      // check never pays for workbench provisioning or a runtime build.
      name: "gui-screenshot-tests",
      testDir: "./tests/gui-screenshot-tests",
      outputDir: "../test-artifacts/playwright/gui-screenshot-tests",
      timeout: 30 * 1000,
      expect: {
        timeout: 10 * 1000,
        toHaveScreenshot: {
          animations: "disabled",
          caret: "hide",
          maxDiffPixels: 0,
          // Ignore only sub-pixel antialiasing noise. Any pixel whose RGB
          // distance exceeds this still fails because maxDiffPixels is zero.
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
      // Lean regression tests: no narration, no artificial delays.
      // No video (avoids the ffmpeg dependency + per-test recording cost);
      // a trace is kept only for failures, which is cheap and debuggable.
      name: "e2e-gui",
      testDir: "./tests/e2e",
      // The review specs are their own project (below), so the authoring suite
      // does not also run them.
      testIgnore: ["**/review/**"],
      outputDir: "../test-artifacts/playwright/e2e-gui",
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
      // The reviewer side of the lifecycle: a golden path that loads an REE
      // this repo authored earlier (examples/rees/) and reproduces all four
      // steps against its evidence, plus one narrow spec for the case it cannot
      // reach — re-fetching a live origin, which that REE does not have. Same
      // lean setup as the e2e-gui project — a regression suite, not a recording —
      // but its own
      // project so a reviewer-facing change can be validated on its own, and
      // with a larger budget: a review re-runs work the author already did, on
      // top of doing it once to have something to review.
      name: "e2e-gui-review",
      testDir: "./tests/e2e/review",
      outputDir: "../test-artifacts/playwright/e2e-gui-review",
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
      // videos never collide with the e2e-gui suite.
      name: "demo-gui",
      testDir: "./tests/demo",
      testIgnore: ["**/code-ocean/**"],
      outputDir: "../test-artifacts/playwright/demo-gui",
      timeout: 300 * 1000,
      expect: { timeout: 10 * 1000 },
      use: {
        ...baseUse,
        video: { mode: "on", size: { width: 1920, height: 1080 } },
        screenshot: "only-on-failure",
      },
    },
    {
      // Long-running, external-image demos. Kept out of `make demo-gui` so the
      // ordinary narrated demo remains quick and self-contained.
      name: "demo-gui-code-ocean",
      testDir: "./tests/demo/code-ocean",
      outputDir: "../test-artifacts/playwright/demo-gui-code-ocean",
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
