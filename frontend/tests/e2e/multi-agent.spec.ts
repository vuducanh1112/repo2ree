import { expect, test } from "./helpers/fixtures";
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
} from "./helpers/flow";

/**
 * Two agents, two concurrent REE creations. The suite runs against whatever
 * stack it is pointed at, so this spec checks the connected-agent count
 * itself and skips on single-agent stacks; `make e2e-tests` / `stack-up`
 * connect E2E_AGENTS (default 2) agents so it normally runs. It pins a
 * session to each of two agents and drives both through a lean creation
 * pipeline —
 * provision, source, metadata, evaluate, seal, release — while the other
 * session stays live.
 *
 * The point is multi-tenancy, not page coverage (the golden-path spec owns
 * that), so the expensive DinD build/activation/experiment stages are skipped
 * and the steps alternate between the sessions: every command lands on a
 * backend that is simultaneously holding a second provisioned bench on the
 * other agent. Session B is sealed and released only *after* A's bench is
 * torn down, so one agent's teardown demonstrably leaves the other's REE
 * intact.
 *
 * Session A uses the default `page` fixture (its cleanup rides the
 * workbenchCleanup auto fixture); session B gets its own browser context and
 * a try/finally teardown of its own.
 */

test.describe("Multi-agent", () => {
  test("two agents host two REE creations side by side", async ({ page, browser }) => {
    // Two provisions (~20-90s each) plus two evaluates and two seals.
    test.setTimeout(10 * 60 * 1000);

    test.skip(
      (await connectedAgentCount(page)) < 2,
      "needs a stack with at least 2 connected agents (E2E_AGENTS=2)",
    );

    const contextB = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
    const pageB = await contextB.newPage();

    try {
      await test.step("pin each session to a different agent", async () => {
        const agentA = await startReeCreation(page, { agentIndex: 0 });
        const agentB = await startReeCreation(pageB, { agentIndex: 1 });
        expect(agentA).toBeTruthy();
        expect(agentB).toBeTruthy();
        expect(agentB).not.toBe(agentA);
      });

      await test.step("provision a workbench on each agent", async () => {
        await provisionWorkbench(page);
        await provisionWorkbench(pageB);
      });

      await test.step("upload source into both workspaces", async () => {
        await expect(await uploadSource(page, pythonHelloWorld())).toBeVisible();
        await expect(await uploadSource(pageB, pythonHelloWorld())).toBeVisible();
      });

      await test.step("give each REE its own metadata", async () => {
        await provideMetadata(page, {
          name: "ree-agent-a",
          version: "1.0.0",
          description: "REE created on the first agent of the multi-agent e2e stack.",
        });
        await provideMetadata(pageB, {
          name: "ree-agent-b",
          version: "1.0.0",
          description: "REE created on the second agent of the multi-agent e2e stack.",
        });

        // Isolation: each session holds its own name, not the other's — the
        // sessions share one backend but must not share intent state.
        const nameField = (p: typeof page) =>
          p.getByPlaceholder("deepfold-protein-structure-prediction");
        await expect(nameField(page)).toHaveValue("ree-agent-a");
        await expect(nameField(pageB)).toHaveValue("ree-agent-b");
      });

      await test.step("run evaluation on both benches", async () => {
        // A real run round-trips through each session's own agent, so this is
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
        // Sealing B is a real backend command through B's agent, issued after
        // A's bench (on the other agent) was torn down.
        await sealRee(pageB);
        await releaseWorkbench(pageB);
      });
    } finally {
      await cleanupWorkbench(pageB).catch(() => {});
      await contextB.close();
    }
  });
});
