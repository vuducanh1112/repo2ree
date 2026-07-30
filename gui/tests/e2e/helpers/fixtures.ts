import { test as base, expect } from "@playwright/test";
import { cleanupWorkbench } from "./flow";

/**
 * e2e `test` with guaranteed workbench teardown.
 *
 * Every e2e test provisions a real workbench container. The `workbenchCleanup`
 * auto fixture seals the REE (so the release control appears) and releases the
 * workbench after the test body runs — including when the test fails — so
 * containers are never left behind. Import `test`/`expect` from here instead of
 * `@playwright/test` in every e2e spec.
 *
 * These specs record no browser coverage. They used to: a `jsCoverage` fixture
 * captured V8 per test and monocart merged it. It was removed because Vite's dev
 * sourcemaps identify sources by basename alone, so all five `index.ts` modules
 * (and 18 files in total) collapsed into one entry — a report that was wrong
 * without saying so. UI coverage belongs to component tests in the `node` tier,
 * where Vitest transforms the files itself and knows their real paths. What these
 * specs still measure is the backend: the stack runs server and agents under
 * coverage.py, which is unaffected.
 */
export const test = base.extend<{
  // biome-ignore lint/suspicious/noConfusingVoidType: value-less auto fixtures; void is the Playwright idiom here
  workbenchCleanup: void;
}>({
  workbenchCleanup: [
    async ({ page }, use) => {
      await use();
      await cleanupWorkbench(page);
    },
    { auto: true },
  ],
});

export { expect };
