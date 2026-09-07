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
  let state = shotStates.get(info);
  if (!state) {
    state = { pages: [], counters: new WeakMap() };
    shotStates.set(info, state);
  }

  let pageIndex = state.pages.indexOf(page);
  if (pageIndex === -1) {
    pageIndex = state.pages.length;
    state.pages.push(page);
  }

  let seq: number;
  if (timing === "before") {
    seq = (state.counters.get(page) ?? 0) + 1;
    state.counters.set(page, seq);
  } else {
    seq = state.counters.get(page) ?? 1;
  }

  const slug =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "step";
  // Preserve historical names for the primary page. Concurrent secondary
  // sessions get a stable lane prefix so their before/after captures cannot
  // overwrite the primary page's files or each other's.
  const lane = pageIndex === 0 ? "" : `${String.fromCharCode(97 + pageIndex)}-`;
  const file = `${lane}${String(seq).padStart(2, "0")}-${slug}-${timing}.png`;

  await page.screenshot({ path: info.outputPath(file) });
}

interface ShotState {
  pages: Page[];
  counters: WeakMap<Page, number>;
}

const shotStates = new WeakMap<ReturnType<typeof test.info>, ShotState>();
