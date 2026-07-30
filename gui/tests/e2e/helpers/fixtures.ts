import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test as base, expect } from "@playwright/test";
import { browserCoverageRawDir } from "../../artifacts";
import { cleanupWorkbench } from "./flow";

// Raw per-test V8 coverage lands under test-artifacts/coverage/browser/raw/<tier>/;
// `scripts/gen-coverage.mjs` merges one tier's captures into that tier's report.
//
// `E2E_COVERAGE_TIER` is both the switch and the destination, deliberately: the
// tier used to be absent from these paths entirely, so a `demo` run overwrote
// whatever an `e2e` run had measured. Making the tier the thing that turns
// coverage on means "measuring, but into no particular tier" is not a state that
// can happen.
const COVERAGE_TIER = process.env.E2E_COVERAGE_TIER;

/**
 * e2e `test` with guaranteed workbench teardown, plus opt-in JS coverage.
 *
 * Every e2e test provisions a real workbench container. The `workbenchCleanup`
 * auto fixture seals the REE (so the release control appears) and releases the
 * workbench after the test body runs — including when the test fails — so
 * containers are never left behind. Import `test`/`expect` from here instead of
 * `@playwright/test` in every e2e spec.
 *
 * When `E2E_COVERAGE_TIER` names a tier, the `jsCoverage` fixture records
 * browser-side V8 coverage for the test and writes it under that tier for later
 * merge. It is declared first so its
 * teardown — stopping coverage —
 * runs last, after the workbench cleanup, capturing the seal/release UI too.
 * With the flag unset it is a no-op, which is what the unmeasured `-on-stack`
 * runs against an image-backed stack rely on.
 */
export const test = base.extend<{
  // biome-ignore lint/suspicious/noConfusingVoidType: value-less auto fixtures; void is the Playwright idiom here
  jsCoverage: void;
  // biome-ignore lint/suspicious/noConfusingVoidType: value-less auto fixtures; void is the Playwright idiom here
  workbenchCleanup: void;
}>({
  jsCoverage: [
    async ({ page }, use) => {
      const enabled = Boolean(COVERAGE_TIER) && Boolean(page.coverage);
      if (enabled) {
        await page.coverage.startJSCoverage({ resetOnNavigation: false });
      }
      await use();
      if (enabled) {
        const entries = await page.coverage.stopJSCoverage();
        const rawDir = browserCoverageRawDir(COVERAGE_TIER as string);
        mkdirSync(rawDir, { recursive: true });
        writeFileSync(join(rawDir, `${test.info().testId}.json`), JSON.stringify(entries));
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
