import { expect, test } from "../helpers/fixtures";
import {
  buildRuntime,
  dockerBuildScript,
  downloadSource,
  generateSbom,
  openReviewConsole,
  provisionWorkbench,
  reproduceBuild,
  reproduceSource,
  startReeCreation,
} from "../helpers/flow";

// The same origin the source review spec fetches — and it carries the demo
// project, so the author's build script can point straight into the clone.
const GIT_ORIGIN_URL = "https://github.com/vuducanh1112/repo2ree.git";
const PROJECT_DIR = "examples/projects/python_hello_world";
const RUNTIME_PATH = `${PROJECT_DIR}/runtime.tar`;

/**
 * The build step of the review lifecycle: rebuild the runtime from the source
 * the review fetched for itself, scan it, and compare the dependency closure
 * with the author's SBOM.
 *
 * ``EQUIVALENT`` rather than ``IDENTICAL`` is the pass this asserts, and that
 * is the point of the step: a docker build embeds timestamps and layer
 * ordering, so two builds of the same input essentially never produce the same
 * bytes. What a reviewer can certify is that the same software got installed.
 */
test.describe("Review build", () => {
  test("rebuilding the runtime certifies an equivalent dependency closure", async ({ page }) => {
    // An author-side build and SBOM, then the reviewer doing both again in
    // isolation — two cold DinD builds plus two scans on one workbench.
    test.setTimeout(20 * 60 * 1000);

    await test.step("author a reviewable REE", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page);
      // Upload-acquired source has no origin to re-fetch, so a reviewable REE
      // needs the download path.
      await downloadSource(page, { url: GIT_ORIGIN_URL, sourceType: "git" });
      await expect(page.getByText(/Resolved to commit/)).toBeVisible({ timeout: 20000 });
      await buildRuntime(page, dockerBuildScript(PROJECT_DIR, RUNTIME_PATH), RUNTIME_PATH);
      // The author's SBOM is the baseline the build comparison certifies
      // against; without it the reviewer's verdict can only be inconclusive.
      await generateSbom(page);
    });

    // Opened once: the HUD toggle flips to "collapse" once expanded, and every
    // step below reads from the same panel.
    const review = await openReviewConsole(page);

    await test.step("reproduce source, which opens the attempt", async () => {
      // Build has nothing to build against until an attempt has fetched source.
      await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeDisabled();
      expect(await reproduceSource(page)).toBe("IDENTICAL");
    });

    await test.step("reproduce the build in the same attempt", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeEnabled();

      expect(await reproduceBuild(page)).toBe("EQUIVALENT");

      // The verdict is stated with the evidence it rests on.
      await expect(review.getByText(/runtime digest: differs/)).toBeVisible();
      await expect(review.getByText(/closure: \d+ matched · 0 missing · 0 extra/)).toBeVisible();
      await expect(
        review.getByText(/review-[0-9a-f]+ · source identical · build equivalent/),
      ).toBeVisible();
    });

    await test.step("the steps with no reviewer path yet stay disabled", async () => {
      await expect(
        review.getByRole("button", { name: "Reproduce Test Activation" }),
      ).toBeDisabled();
      await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
    });
  });
});
