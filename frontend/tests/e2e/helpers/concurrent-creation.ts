import type { Browser, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import {
  cleanupWorkbench,
  connectedAgentCount,
  main,
  provideMetadata,
  provisionWorkbench,
  pythonHelloWorld,
  releaseWorkbench,
  runEvaluate,
  sealRee,
  startReeCreation,
  uploadSource,
} from "./flow";

/**
 * The shared body of the concurrent-creation specs: two sessions run REE
 * creation at the same time, pinned to the agents named by `agentIndexes`.
 * Both drive the same lean pipeline — provision, source, metadata, evaluate,
 * seal, release — while the other session stays live, so every command lands
 * on a backend that is simultaneously holding a second provisioned bench.
 *
 * The point is tenancy, not page coverage (the golden-path spec owns that),
 * so the expensive DinD build/activation/experiment stages are skipped and
 * the steps alternate between the sessions. Session B is sealed and released
 * only *after* A's bench is torn down, so one REE's teardown demonstrably
 * leaves the other intact.
 *
 * Session A uses the caller's `page` fixture (its cleanup rides the
 * workbenchCleanup auto fixture); session B gets its own browser context and
 * a try/finally teardown of its own.
 *
 * Exported as a test *body* (not a `test()` factory) so each spec declares
 * its own test and failures report against the spec file, not this helper.
 */
export async function twoConcurrentCreations(
  page: Page,
  browser: Browser,
  options: { agentIndexes: [number, number]; sameAgent: boolean },
) {
  // Two provisions (~20-90s each) plus two evaluates and two seals.
  test.setTimeout(10 * 60 * 1000);

  if (!options.sameAgent) {
    test.skip(
      (await connectedAgentCount(page)) < 2,
      "needs a stack with at least 2 connected agents (E2E_AGENTS=2)",
    );
  }

  const contextB = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const pageB = await contextB.newPage();

  try {
    await test.step("pin each session to its agent", async () => {
      const agentA = await startReeCreation(page, { agentIndex: options.agentIndexes[0] });
      const agentB = await startReeCreation(pageB, { agentIndex: options.agentIndexes[1] });
      expect(agentA).toBeTruthy();
      expect(agentB).toBeTruthy();
      if (options.sameAgent) {
        expect(agentB).toBe(agentA);
      } else {
        expect(agentB).not.toBe(agentA);
      }
    });

    await test.step("provision a workbench for each session", async () => {
      await provisionWorkbench(page);
      await provisionWorkbench(pageB);
    });

    await test.step("upload source into both workspaces", async () => {
      await expect(await uploadSource(page, pythonHelloWorld())).toBeVisible();
      await expect(await uploadSource(pageB, pythonHelloWorld())).toBeVisible();
    });

    await test.step("give each REE its own metadata", async () => {
      await provideMetadata(page, {
        name: "ree-session-a",
        version: "1.0.0",
        description: "REE created by the first of two concurrent sessions.",
      });
      await provideMetadata(pageB, {
        name: "ree-session-b",
        version: "1.0.0",
        description: "REE created by the second of two concurrent sessions.",
      });

      // Isolation: each session holds its own name, not the other's — the
      // sessions share one backend (and in the same-agent variant one
      // agent) but must not share intent state.
      const nameField = (p: Page) => p.getByPlaceholder("deepfold-protein-structure-prediction");
      await expect(nameField(page)).toHaveValue("ree-session-a");
      await expect(nameField(pageB)).toHaveValue("ree-session-b");
    });

    await test.step("run evaluation on both benches", async () => {
      // A real run round-trips through each session's own bench, so this is
      // the check that commands route to the bench they belong to.
      await runEvaluate(page);
      await runEvaluate(pageB);
      await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
      await expect(main(pageB).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
    });

    await test.step("seal and release A while B stays live", async () => {
      await sealRee(page);
      await releaseWorkbench(page);
    });

    await test.step("B survives A's teardown: seal and release it too", async () => {
      // Sealing B is a real backend command through B's bench, issued after
      // A's bench was torn down.
      await sealRee(pageB);
      await releaseWorkbench(pageB);
    });
  } finally {
    await cleanupWorkbench(pageB).catch(() => {});
    await contextB.close();
  }
}
