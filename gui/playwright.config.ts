import { defineConfig } from "@playwright/test";
import { recordRuntime, testRunDir } from "./testArtifacts.cjs";

recordRuntime("browser");

// When E2E_BASE_URL is set, the tests run against an externally provided
// GUI (e.g. the compose image stack on :3000) and no vite dev server is
// started. Default: playwright starts its own dev server on :4173.
const externalBaseURL = process.env.E2E_BASE_URL;
// Source-run stacks reserve a fresh API port for every invocation and pass it
// here. Vite proxies the browser to that exact process; browser-only suites and
// direct local Playwright runs retain the conventional :8000 fallback.
const apiBaseURL = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
// A per-test stack names a dev-server port of its own (stacks run side by side,
// each proxying to its own API), and that server must be its own: never reused,
// never moved to another port.
const ownGuiPort = process.env.E2E_GUI_PORT;
const guiPort = ownGuiPort ?? "4173";

// Per-test backstop for projects whose runs pull, fetch, or build over the network.
// Each run is bounded by its own stall window (tests/runs.ts), not by this.
const NETWORK_TEST_TIMEOUT = 45 * 60 * 1000;

const baseUse = {
  baseURL: externalBaseURL ?? `http://127.0.0.1:${guiPort}`,
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
  // A testbed-recorded run (repo2ree_testbed record) also asks for a JUnit report, which it
  // turns into the run's record; the list stays what a person watching sees.
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
      // WCAG 2.2 AA, axe best-practice, and focused text-contrast checks over
      // the same deterministic application states as the screenshot suite.
      // Axe results are attached for review and debugging.
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
      // Page-level visual regression tests. These render the real routed GUI,
      // but fulfill the HTTP contract from deterministic fixtures so a visual
      // check never pays for workbench provisioning or a runtime build.
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
      // Real projects through the whole lifecycle, one scenario per spec: their
      // own toolchains (pip, a Dockerfile, Maven), base images pinned by digest
      // and pulled through the machine's registry mirror, packages pinned by
      // hash, origins served by the stack itself. Run per test, each on a fresh
      // stack whose behaviour is judged like the assurance tiers'. No video;
      // a trace only for failures.
      name: "showcase",
      testDir: "./tests/showcase",
      outputDir: `${testRunDir}/browser/tests/showcase`,
      // A backstop only: every run is watched (tests/runs.ts), and fails when it
      // goes quiet, so a slow network costs time rather than a failure.
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
      // The instant fixture through the GUI: every stage on a bench without a
      // Docker daemon and with nothing to download, so a spec takes seconds per
      // stage. Screenshots before and after each step are kept for inspection.
      name: "e2e-gui-instant",
      testDir: "./tests/e2e-instant",
      metadata: { runWatch: "instant" },
      outputDir: `${testRunDir}/browser/tests/e2e-gui-instant`,
      // The authoring spec takes ~70s alone but ~130-140s in the assurance gate,
      // which runs this suite beside the system tier; 120s failed it on load.
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
      // The recorded walkthrough: the Python Docker showcase scenario itself,
      // narrated (tests/showcase/narration.ts draws its captions only here) and
      // paced, with video on. The video is the artifact, so no trace.
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
