import { expect, type Page, test } from "@playwright/test";
import { stepShot } from "../screenshot";

/**
 * Download the REE as its author would and keep it in this test's output
 * directory. The stack's collector finds kept archives there and records each
 * REE's Git history as behaviour evidence, so every spec that authors an REE
 * calls this before releasing its workbench.
 */
export async function keepReeArchive(page: Page, name = "ree.zip") {
  await stepShot(page, "download-ree", "before");
  const download = page.getByRole("banner").getByRole("button", { name: /Download REE/ });
  await expect(download).toBeEnabled();
  const [file] = await Promise.all([page.waitForEvent("download"), download.click()]);
  const target = test.info().outputPath(name);
  await file.saveAs(target);
  await stepShot(page, "download-ree", "after");
  return target;
}
