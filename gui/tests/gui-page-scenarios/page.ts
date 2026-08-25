import { expect, type Page } from "@playwright/test";
import { VISUAL_REE_ID } from "./scenario";

export async function settleVisualPage(page: Page): Promise<void> {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await page.addStyleTag({
    content:
      "*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }",
  });
}

export async function openVisualWorkspace(page: Page): Promise<void> {
  await page.goto(`/workspace?reeId=${VISUAL_REE_ID}`);
  await expect(page.getByRole("banner").getByText("climate-model-lab")).toBeVisible();
  // The canvas navigation is a zero-sized semantic wrapper around absolutely
  // positioned node buttons, so the wrapper itself is intentionally "hidden"
  // to Playwright even though its controls are painted and interactive.
  await expect(
    page
      .getByRole("navigation", { name: "Workspace pages" })
      .getByRole("button", { name: "Source", exact: true }),
  ).toBeVisible();
  await settleVisualPage(page);
}

export async function openWorkspacePage(page: Page, label: string): Promise<void> {
  await openVisualWorkspace(page);
  await page
    .getByRole("navigation", { name: "Workspace pages" })
    .getByRole("button", { name: label, exact: true })
    .click();
  await settleVisualPage(page);
}
