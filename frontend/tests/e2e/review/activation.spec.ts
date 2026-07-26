import { expect, test } from "../helpers/fixtures";
import {
  buildRuntime,
  dockerBuildScript,
  dockerRunScript,
  generateSbom,
  openReviewConsole,
  provisionWorkbench,
  pythonHelloWorld,
  reproduceActivation,
  reproduceBuild,
  reproduceSource,
  startReeCreation,
  testActivation,
  uploadSource,
} from "../helpers/flow";

const PROJECT_DIR = "python_hello_world";
const RUNTIME_PATH = `${PROJECT_DIR}/runtime.tar`;

/**
 * The activation step of the review lifecycle: does the runtime this attempt
 * certified actually come up?
 *
 * The step certifies nothing by comparison, and that is the whole point of
 * pinning it end to end. Source and build each diff the reviewer's result
 * against a recorded author artifact; activation has none to diff against, so
 * what has to hold instead is that it ran the author's own script *in the
 * reviewer's workspace*, against the runtime the build step certified — not the
 * author's, and not one the attempt never accounted for.
 *
 * It also depends on something no earlier spec could observe: the build leaving
 * its workspace behind. On an independent basis the rebuilt runtime exists
 * nowhere else, so an attempt that reclaimed it has nothing left to activate.
 */
test.describe("Review activation", () => {
  test("probes the runtime the attempt certified, in the attempt's own workspace", async ({
    page,
  }) => {
    // Two cold DinD builds, two scans, and two container runs on one workbench.
    test.setTimeout(25 * 60 * 1000);

    await test.step("author an REE that builds and activates", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page);
      await uploadSource(page, pythonHelloWorld());
      await buildRuntime(page, dockerBuildScript(PROJECT_DIR, RUNTIME_PATH), RUNTIME_PATH);
      await generateSbom(page);
      // The author's own probe. It is a precondition of a credible baseline
      // rather than a baseline the reviewer reproduces — the review below never
      // compares against it, it just needs a script that exists to run.
      await testActivation(page, dockerRunScript('python -c "print(1)"', RUNTIME_PATH));
    });

    const review = await openReviewConsole(page);

    await test.step("reproduce source and build, which leaves a runnable workspace", async () => {
      expect(await reproduceSource(page)).toBe("IDENTICAL");
      expect(["IDENTICAL", "EQUIVALENT"]).toContain(await reproduceBuild(page));
    });

    await test.step("activation is offered only once a runtime has been certified", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeEnabled();
    });

    await test.step("the reviewer's own runtime comes up", async () => {
      expect(await reproduceActivation(page)).toBe("COMPLETE");

      await expect(review.getByText("activation: the runtime is inhabitable")).toBeVisible();
      await expect(
        review.getByText(
          /review-[0-9a-f]+ · source identical · build (identical|equivalent) · activation succeeded/,
        ),
      ).toBeVisible();
    });

    await test.step("experiments stay disabled, having no reviewer path yet", async () => {
      // Their dependency has settled — activation vouched for the runtime they
      // would run in — so what holds them back is the missing handler, not the
      // DAG. That is the next step to build.
      await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
    });
  });
});
