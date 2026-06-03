import { test as base, expect } from "@playwright/test";
import { cleanupWorkbench } from "./flow";

/**
 * e2e `test` with guaranteed workbench teardown.
 *
 * Every e2e test provisions a real workbench container. This auto fixture
 * seals the REE (so the release control appears) and releases the workbench
 * after the test body runs — including when the test fails — so containers are
 * never left behind. Import `test`/`expect` from here instead of
 * `@playwright/test` in every e2e spec.
 */
// biome-ignore lint/suspicious/noConfusingVoidType: value-less auto fixture; void is the Playwright idiom here
export const test = base.extend<{ workbenchCleanup: void }>({
  workbenchCleanup: [
    async ({ page }, use) => {
      await use();
      await cleanupWorkbench(page);
    },
    { auto: true },
  ],
});

export { expect };
