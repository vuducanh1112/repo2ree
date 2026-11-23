import { expect, test } from "@playwright/test";

test("baselines match this renderer", async ({ browser }) => {
  expect(
    browser.version(),
    "The renderer changed — it moves when nix/devshell.nix's playwright-driver does. " +
      "Any pixel diffs below are chromium, not the GUI. Redraw both the baselines and this " +
      "record with `just update-gui-screenshot-baselines`, and review the resulting PNG diff.",
  ).toMatchSnapshot("baseline-chromium-version.txt");
});
