import { type Page, test } from "@playwright/test";

/**
 * Capture a named, ordered screenshot at the start or end of a step.
 *
 * Call with `'before'` at the top of a step (increments the counter and writes
 * `01-slug-before.png`) and with `'after'` at the bottom (reuses the same
 * counter and writes `01-slug-after.png`). Together they give a before/after
 * pair for every step, all sorted in execution order.
 *
 * Files land in the test's Playwright output dir, e.g.:
 *   test-artifacts/playwright/<project>/<test>/01-provision-workbench-before.png
 *   test-artifacts/playwright/<project>/<test>/01-provision-workbench-after.png
 */
export async function stepShot(page: Page, name: string, timing: "before" | "after") {
  const info = test.info();

  let seq: number;
  if (timing === "before") {
    seq = (stepCounters.get(info) ?? 0) + 1;
    stepCounters.set(info, seq);
  } else {
    seq = stepCounters.get(info) ?? 1;
  }

  const slug =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "step";
  const file = `${String(seq).padStart(2, "0")}-${slug}-${timing}.png`;

  await page.screenshot({ path: info.outputPath(file) });
}

const stepCounters = new WeakMap<ReturnType<typeof test.info>, number>();
