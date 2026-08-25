import type { Badges } from "../ree/ReeTypes";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import { type AppShellPage, PAGE } from "./pages";
import { PROCESS_STEPS, resolveNavCompleted } from "./processSteps";

export interface AuthoringStep {
  key: string;
  order: number;
  label: string;
  requires: readonly string[];
  actions: readonly string[];
}

export type AuthoringStepStatus = "complete" | "ready" | "blocked";

const PAGE_BY_STEP: Readonly<Record<string, AppShellPage>> = {
  source: PAGE.SOURCE,
  metadata: PAGE.METADATA,
  hbom: PAGE.HBOM,
  evaluate: PAGE.EVALUATE,
  build: PAGE.BUILD,
  sbom: PAGE.SBOM,
  // The cross-check is the second operation on the SBOM page.
  crosscheck: PAGE.SBOM,
  activation: PAGE.ACTIVATION,
  experiments: PAGE.EXPERIMENTS,
  seal: PAGE.SEAL,
};

const PROCESS_STEP_BY_KEY = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

export function authoringPageForStep(key: string): AppShellPage | undefined {
  return PAGE_BY_STEP[key];
}

function isAuthoringStepComplete(key: string, ree: ReeEditorViewModel, badges: Badges): boolean {
  if (key === "crosscheck") return badges.crosscheck === true || badges.crosscheck === "succeeded";
  const page = authoringPageForStep(key);
  const processStep = page ? PROCESS_STEP_BY_KEY.get(page) : undefined;
  return processStep ? resolveNavCompleted(processStep, ree, badges) : false;
}

export function authoringStepStatuses(
  steps: readonly AuthoringStep[],
  ree: ReeEditorViewModel,
  badges: Badges,
): Readonly<Record<string, AuthoringStepStatus>> {
  const completed = new Set(
    steps.filter((step) => isAuthoringStepComplete(step.key, ree, badges)).map((step) => step.key),
  );
  return Object.fromEntries(
    steps.map((step) => [
      step.key,
      completed.has(step.key)
        ? "complete"
        : step.requires.every((required) => completed.has(required))
          ? "ready"
          : "blocked",
    ]),
  );
}
