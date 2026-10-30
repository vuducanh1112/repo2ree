import { twoConcurrentCreations } from "../helpers/concurrent-creation";
import { test } from "../helpers/fixtures";

/**
 * Two labs, two concurrent REE creations — the topology where the control
 * plane must route each session's commands to the lab its REE is pinned
 * to, and one lab's teardown must not disturb the other's REE. The shared
 * pipeline lives in helpers/concurrent-creation.ts. Two REEs on one lab are
 * the system tier's (test_two_rees_author_side_by_side).
 *
 * The suite runs against whatever stack it is pointed at, so this spec
 * checks the connected-lab count itself and skips on single-lab stacks;
 * `just test-showcase` and `just stack-up locations=2` both connect 2 labs.
 */

test.describe("Multi-lab", () => {
  test("two labs host two REE creations side by side", async ({ page, browser }) => {
    await twoConcurrentCreations(page, browser, { labIndexes: [0, 1], sameLab: false });
  });
});
