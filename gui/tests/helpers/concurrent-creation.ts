import type { Browser, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import {
  cleanupWorkbench,
  connectedLabCount,
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

export async function twoConcurrentCreations(
  page: Page,
  browser: Browser,
  options: { labIndexes: [number, number]; sameLab: boolean },
) {
  if (!options.sameLab) {
    test.skip(
      (await connectedLabCount(page)) < 2,
      "needs a stack with at least 2 connected labs (just test-showcase)",
    );
  }

  const contextB = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const pageB = await contextB.newPage();

  try {
    await test.step("pin each session to its lab", async () => {
      const [labA, labB] = await Promise.all([
        startReeCreation(page, { labIndex: options.labIndexes[0] }),
        startReeCreation(pageB, { labIndex: options.labIndexes[1] }),
      ]);
      expect(labA).toBeTruthy();
      expect(labB).toBeTruthy();
      if (options.sameLab) {
        expect(labB).toBe(labA);
      } else {
        expect(labB).not.toBe(labA);
      }
    });

    await test.step("provision a workbench for each session", async () => {
      const provisionA = () => provisionWorkbench(page);
      const provisionB = () => provisionWorkbench(pageB);

      await Promise.all([provisionA(), provisionB()]);
    });

    await test.step("upload source into both workspaces", async () => {
      const [clearA, clearB] = await Promise.all([
        uploadSource(page, pythonHelloWorld()),
        uploadSource(pageB, pythonHelloWorld()),
      ]);
      await Promise.all([expect(clearA).toBeVisible(), expect(clearB).toBeVisible()]);
    });

    await test.step("give each REE its own metadata", async () => {
      await Promise.all([
        provideMetadata(page, {
          name: "ree-session-a",
          version: "1.0.0",
          description: "REE created by the first of two concurrent sessions.",
        }),
        provideMetadata(pageB, {
          name: "ree-session-b",
          version: "1.0.0",
          description: "REE created by the second of two concurrent sessions.",
        }),
      ]);

      const nameField = (p: Page) => p.getByPlaceholder("deepfold-protein-structure-prediction");
      await expect(nameField(page)).toHaveValue("ree-session-a");
      await expect(nameField(pageB)).toHaveValue("ree-session-b");
    });

    await test.step("run evaluation on both benches", async () => {
      await Promise.all([runEvaluate(page), runEvaluate(pageB)]);
      await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
      await expect(main(pageB).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
    });

    await test.step("seal and release A while B stays live", async () => {
      await sealRee(page);
      await releaseWorkbench(page);
    });

    await test.step("B survives A's teardown: seal and release it too", async () => {
      await sealRee(pageB);
      await releaseWorkbench(pageB);
    });
  } finally {
    await cleanupWorkbench(pageB).catch(() => {});
    await contextB.close();
  }
}
