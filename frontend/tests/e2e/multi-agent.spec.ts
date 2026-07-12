import { twoConcurrentCreations } from "./helpers/concurrent-creation";
import { test } from "./helpers/fixtures";

/**
 * Two agents, two concurrent REE creations — the topology where the control
 * plane must route each session's commands to the agent its REE is pinned
 * to, and one agent's teardown must not disturb the other's REE. The shared
 * pipeline lives in helpers/concurrent-creation.ts; the same-agent topology
 * has its own spec (same-agent-sessions.spec.ts).
 *
 * The suite runs against whatever stack it is pointed at, so this spec
 * checks the connected-agent count itself and skips on single-agent stacks;
 * `make e2e-tests` / `stack-up` connect E2E_AGENTS (default 2) agents so it
 * normally runs.
 */

test.describe("Multi-agent", () => {
  test("two agents host two REE creations side by side", async ({ page, browser }) => {
    await twoConcurrentCreations(page, browser, { agentIndexes: [0, 1], sameAgent: false });
  });
});
