import { expect, test } from "../helpers/fixtures";
import {
  buildRuntime,
  dockerBuildScript,
  generateSbom,
  openReviewConsole,
  provisionWorkbench,
  pythonHelloWorld,
  reproduceBuild,
  reproduceSource,
  selectReviewBasis,
  startReeCreation,
  uploadSource,
} from "../helpers/flow";

// The demo project, uploaded rather than fetched. The REE then carries its own
// source and nothing here depends on what a remote happens to be serving.
const PROJECT_DIR = "python_hello_world";
const RUNTIME_PATH = `${PROJECT_DIR}/runtime.tar`;

/**
 * The build step of the review lifecycle, over an REE that carries its own
 * source — the case a bundle always presents.
 *
 * The point of driving it from an upload is that the two steps settle on
 * *different* bases without the reviewer choosing either: there is no origin to
 * fetch, so the source comes from the REE's own snapshot; but the recipe is
 * right there, so the runtime is genuinely rebuilt from that source. Carrying
 * its own source costs an REE nothing in reproducibility — that is the claim
 * this spec pins.
 *
 * The rebuild passes as either ``EQUIVALENT`` or ``IDENTICAL``, and which one
 * is not the test's business: a docker build embeds timestamps and layer
 * ordering, so matching bytes depend on what the daemon had cached. What a
 * reviewer can always certify is that the same software got installed, so the
 * closure counts are asserted exactly and the digest tier is left to say
 * whatever the environment earned.
 */
const REBUILD_PASSES = ["IDENTICAL", "EQUIVALENT"];
test.describe("Review build", () => {
  test("rebuilding from the REE's own source certifies an equivalent closure", async ({ page }) => {
    // An author-side build and SBOM, then the reviewer doing both again in
    // isolation — two cold DinD builds plus three scans on one workbench.
    test.setTimeout(20 * 60 * 1000);

    await test.step("author a reviewable REE from an uploaded source", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page);
      await uploadSource(page, pythonHelloWorld());
      await buildRuntime(page, dockerBuildScript(PROJECT_DIR, RUNTIME_PATH), RUNTIME_PATH);
      // The author's SBOM is the baseline the build comparison certifies
      // against; without it the reviewer's verdict can only be inconclusive.
      await generateSbom(page);
    });

    // Opened once: the HUD toggle flips to "collapse" once expanded, and every
    // step below reads from the same panel.
    const review = await openReviewConsole(page);

    await test.step("reproduce source, which opens the attempt", async () => {
      // Build has nothing to build against until an attempt has acquired source.
      await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeDisabled();
      // Left on the default basis: with no origin to fetch there is only one
      // way to get a tree, and the reviewer should not have to know that.
      expect(await reproduceSource(page)).toBe("IDENTICAL");
      await expect(review.getByText(/^source verified from the REE's own artifacts/)).toBeVisible();
    });

    await test.step("reproduce the build in the same attempt", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeEnabled();

      expect(REBUILD_PASSES).toContain(await reproduceBuild(page));

      // The runtime was rebuilt, not taken from the REE — a bundled source does
      // not weaken the step that follows it.
      await expect(review.getByText(/source and runtime verified/)).toHaveCount(0);
      // The verdict is stated with the evidence it rests on.
      await expect(review.getByText(/closure: \d+ matched · 0 missing · 0 extra/)).toBeVisible();
      await expect(
        review.getByText(/review-[0-9a-f]+ · source identical · build (identical|equivalent)/),
      ).toBeVisible();
    });

    await test.step("a second attempt certifies the runtime the REE already carries", async () => {
      // The other basis, chosen deliberately: no rebuild, just a scan of the
      // artifact this REE ships. It is the very file the author's evidence
      // describes, so the digest tier settles this one whatever the daemon
      // cached — the one case where IDENTICAL is guaranteed, not earned.
      await selectReviewBasis(page, "From bundle");
      expect(await reproduceSource(page)).toBe("IDENTICAL");
      expect(await reproduceBuild(page)).toBe("IDENTICAL");

      await expect(review.getByText(/^source and runtime verified from the REE's/)).toBeVisible();
      await expect(review.getByText(/runtime digest: bit-identical/)).toBeVisible();
    });

    await test.step("a settled build opens activation, and nothing beyond it", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeEnabled();
      await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
    });
  });
});
