import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test as base, expect } from "@playwright/test";
import { cleanupWorkbench } from "./flow";

// Raw per-test V8 coverage lands here; `scripts/gen-coverage.mjs`
// merges it into the report. Under test-artifacts/ (the one gitignored root for
// all test output) alongside the generated coverage/.
const COVERAGE_RAW_DIR = join(process.cwd(), "test-artifacts", "coverage-raw");

/**
 * e2e `test` with guaranteed workbench teardown, plus opt-in JS coverage.
 *
 * Every e2e test provisions a real workbench container. The `workbenchCleanup`
 * auto fixture seals the REE (so the release control appears) and releases the
 * workbench after the test body runs — including when the test fails — so
 * containers are never left behind. Import `test`/`expect` from here instead of
 * `@playwright/test` in every e2e spec.
 *
 * When `E2E_COVERAGE` is set, the `jsCoverage` fixture records browser-side V8
 * coverage for the test and writes it to disk for later merge (`make
 * e2e-coverage`). It is declared first so its teardown — stopping coverage —
 * runs last, after the workbench cleanup, capturing the seal/release UI too.
 * With the flag unset it is a no-op, so a plain `make e2e-tests` pays nothing.
 */
export const test = base.extend<{
  // biome-ignore lint/suspicious/noConfusingVoidType: value-less auto fixtures; void is the Playwright idiom here
  jsCoverage: void;
  // biome-ignore lint/suspicious/noConfusingVoidType: value-less auto fixtures; void is the Playwright idiom here
  workbenchCleanup: void;
}>({
  jsCoverage: [
    async ({ page }, use) => {
      const enabled = Boolean(process.env.E2E_COVERAGE) && Boolean(page.coverage);
      if (enabled) {
        await page.coverage.startJSCoverage({ resetOnNavigation: false });
      }
      await use();
      if (enabled) {
        const entries = await page.coverage.stopJSCoverage();
        mkdirSync(COVERAGE_RAW_DIR, { recursive: true });
        writeFileSync(
          join(COVERAGE_RAW_DIR, `${test.info().testId}.json`),
          JSON.stringify(entries),
        );
      }
    },
    { auto: true },
  ],
  workbenchCleanup: [
    async ({ page }, use) => {
      await use();
      await cleanupWorkbench(page);
    },
    { auto: true },
  ],
});

export { expect };
