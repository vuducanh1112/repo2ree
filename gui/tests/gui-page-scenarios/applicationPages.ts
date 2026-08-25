import { expect, type Page } from "@playwright/test";
import { openVisualWorkspace, openWorkspacePage, settleVisualPage } from "./page";

interface ApplicationPageScenario {
  name: string;
  screenshot: string;
  contrastRoot?: string;
  prepare: (page: Page) => Promise<void>;
}

export const applicationPageScenarios: ApplicationPageScenario[] = [
  {
    name: "landing page",
    screenshot: "landing.png",
    prepare: async (page) => {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "REE Workspace" })).toBeVisible();
      await settleVisualPage(page);
    },
  },
  {
    name: "lab location picker",
    screenshot: "lab-location.png",
    prepare: async (page) => {
      await page.goto("/lab-location");
      await expect(page.getByRole("heading", { name: "Choose a lab location" })).toBeVisible();
      await expect(page.getByText("lab-oslo-01")).toBeVisible();
      await settleVisualPage(page);
    },
  },
  {
    name: "workbench setup",
    screenshot: "workbench-setup.png",
    prepare: async (page) => {
      await page.goto("/workspace?agentId=agent-oslo");
      await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
      await expect(page.getByText("Python 3.12")).toBeVisible();
      await settleVisualPage(page);
    },
  },
  {
    name: "REE index",
    screenshot: "ree-index.png",
    prepare: async (page) => {
      await page.goto("/ree-index");
      await expect(page.getByRole("heading", { name: "REE Index" })).toBeVisible();
      await expect(page.getByText("climate-model-lab")).toBeVisible();
      await settleVisualPage(page);
    },
  },
  {
    name: "authored workspace hub",
    screenshot: "workspace-hub.png",
    prepare: openVisualWorkspace,
  },
  {
    name: "authoring navigation",
    screenshot: "authoring-navigation.png",
    prepare: async (page) => {
      await openVisualWorkspace(page);
      await page.getByRole("button", { name: "Expand workflow" }).click();
      await expect(page.getByRole("navigation", { name: "Authoring workflow" })).toBeVisible();
      await settleVisualPage(page);
    },
  },
  {
    name: "completed review",
    screenshot: "review-complete.png",
    contrastRoot: '[data-canvas-hud="true"]',
    prepare: async (page) => {
      await openVisualWorkspace(page);
      await page.getByRole("button", { name: "Expand workflow" }).click();
      await page.getByRole("tab", { name: /Review/ }).click();
      await expect(page.getByText("RESULTS · 1/1 REPRODUCED")).toBeVisible();
      await settleVisualPage(page);
    },
  },
  workspaceScenario(
    "source workspace",
    "source-workspace.png",
    "Source",
    async (page) => {
      await expect(page.getByRole("region", { name: "Workspace Snapshot" })).toBeVisible();
    },
    "Source Acquisition",
  ),
  workspaceScenario("metadata editor", "metadata.png", "Metadata", async (page) => {
    await expect(page.getByRole("textbox", { name: "REE Name" })).toHaveValue("climate-model-lab");
  }),
  workspaceScenario("hardware bill of materials", "hardware-bom.png", "Hardware", async (page) => {
    await expect(page.locator('input[value="Intel Xeon Gold 6338"]')).toBeVisible();
  }),
  workspaceScenario(
    "reproducibility readiness",
    "evaluate-complete.png",
    "Reproducibility Readiness",
    async (page) => {
      await expect(page.getByText("Base image tag is mutable")).toBeVisible();
    },
  ),
  workspaceScenario("build runtime", "build-runtime.png", "Build", async (page) => {
    await expect(page.getByRole("heading", { name: "Build Runtime" })).toBeVisible();
  }),
  workspaceScenario("software bill of materials", "sbom.png", "SBOM", async (page) => {
    await expect(page.getByRole("heading", { name: "Generate SBOM" })).toBeVisible();
  }),
  workspaceScenario("activation", "activation.png", "Activation", async (page) => {
    await expect(page.getByRole("heading", { name: "Test Activation" })).toBeVisible();
  }),
  workspaceScenario("experiments", "experiments.png", "Experiments", async (page) => {
    await expect(page.getByRole("button", { name: "EXP-001 regional-forecast" })).toBeVisible();
  }),
  workspaceScenario("archive", "archive.png", "Archive", async (page) => {
    await expect(page.getByRole("heading", { name: "Deposit & Share" })).toBeVisible();
  }),
  workspaceScenario("seal readiness", "seal-ready.png", "Seal", async (page) => {
    await expect(page.getByRole("button", { name: "Seal anyway" })).toBeVisible();
  }),
];

function workspaceScenario(
  name: string,
  screenshot: string,
  pageLabel: string,
  assertReady: (page: Page) => Promise<void>,
  contrastLabel = pageLabel,
): ApplicationPageScenario {
  return {
    name,
    screenshot,
    contrastRoot: `section[aria-label="${contrastLabel}"]`,
    prepare: async (page) => {
      await openWorkspacePage(page, pageLabel);
      await assertReady(page);
    },
  };
}
