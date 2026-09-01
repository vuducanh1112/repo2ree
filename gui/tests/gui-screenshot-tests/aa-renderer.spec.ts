import { expect, test } from "@playwright/test";

// The baselines in application-pages.screenshot.spec.ts-snapshots/ are bit-exact
// against one renderer: playwright.config.ts sets maxDiffPixels: 0, so a chromium
// bump invalidates every one of them at once. That arrives as a dozen-plus red
// screenshot tests which read exactly like a CSS regression until you open the
// diff images — the pixel counts are the same order of magnitude as a dropped
// icon or a 2px misalignment, which is why the tolerance stays at zero.
//
// This guard resolves the ambiguity before those tests run. The `aa-` prefix is
// what puts it first: the suite runs workers: 1 / fullyParallel: false, so spec
// files execute in filename order (the same convention that sorts zz-inspect
// last).
//
// The version is recorded as a snapshot rather than a constant in this file, so
// `--update-snapshots` refreshes it in the same pass that redraws the PNGs and
// the two can never disagree about which renderer drew them. Deriving it from
// the running browser instead would make the assertion a tautology: the whole
// job here is to compare the live renderer against the recorded one.
test("baselines match this renderer", async ({ browser }) => {
  expect(
    browser.version(),
    "The renderer changed — it moves when nix/devshell.nix's playwright-driver does. " +
      "Any pixel diffs below are chromium, not the GUI. Redraw both the baselines and this " +
      "record with `just gui-screenshot-baselines`, and review the resulting PNG diff.",
  ).toMatchSnapshot("baseline-chromium-version.txt");
});
