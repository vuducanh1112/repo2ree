import { twoConcurrentCreations } from "./helpers/concurrent-creation";
import { test } from "./helpers/fixtures";

/**
 * One agent, two concurrent REE creations — the multi-user topology where
 * two sessions share a single agent, so bench containers, workspace volumes,
 * and run dispatch must stay isolated per REE on one host. The shared
 * pipeline lives in helpers/concurrent-creation.ts; the two-agent topology
 * has its own spec (multi-agent.spec.ts).
 *
 * Needs only one connected agent, so unlike the multi-agent spec it runs on
 * every stack, single-agent ones included.
 */

test.describe("Same-agent sessions", () => {
  test("one agent hosts two REE creations side by side", async ({ page, browser }) => {
    await twoConcurrentCreations(page, browser, { agentIndexes: [0, 0], sameAgent: true });
  });
});
