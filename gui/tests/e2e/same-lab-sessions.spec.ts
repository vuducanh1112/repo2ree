import { twoConcurrentCreations } from "./helpers/concurrent-creation";
import { test } from "./helpers/fixtures";

/**
 * One lab, two concurrent REE creations — the multi-user topology where
 * two sessions share a single lab, so bench containers, workspace volumes,
 * and run dispatch must stay isolated per REE on one host. The shared
 * pipeline lives in helpers/concurrent-creation.ts; the two-lab topology
 * has its own spec (multi-lab.spec.ts).
 *
 * Needs only one connected lab, so unlike the multi-lab spec it runs on
 * every stack, single-lab ones included.
 */

test.describe("Same-lab sessions", () => {
  test("one lab hosts two REE creations side by side", async ({ page, browser }) => {
    await twoConcurrentCreations(page, browser, { labIndexes: [0, 0], sameLab: true });
  });
});
