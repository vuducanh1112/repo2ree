import { test as base, expect } from "@playwright/test";
import { cleanupWorkbench } from "./flow";

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
