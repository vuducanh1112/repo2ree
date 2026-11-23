import { twoConcurrentCreations } from "../helpers/concurrent-creation";
import { test } from "../helpers/fixtures";

test.describe("Multi-lab", () => {
  test("two labs host two REE creations side by side", async ({ page, browser }) => {
    await twoConcurrentCreations(page, browser, { labIndexes: [0, 1], sameLab: false });
  });
});
