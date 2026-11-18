import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import {
  AUTHORING_STEP_KEYS,
  type AuthoringStepKey,
  isAuthoringStepComplete,
} from "@core/ree/AuthoringProgress";
import { type Badges, isSuccessfulStepOutcome } from "@core/ree/ReeTypes";
import type { EvidenceStep } from "@core/ree/StepEvidence";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import type { ReeStepDefinition } from "@core/ree-steps/stepTypes";

interface ProcessStep {
  n: number;
  key: AppShellPage;
  label: string;
  automation: ReeStepDefinition | null;
  desc: string;
  navCompleted?: (ree: ReeEditorViewModel, badges: Badges) => boolean;
}

const AUTOMATION_BY_KEY: Record<string, ReeStepDefinition> = Object.fromEntries(
  REE_STEPS.map((step) => [step.key, step]),
) as Record<string, ReeStepDefinition>;

// Workbench is intentionally absent: it IS the canvas (the lab), not a ring
// node. Its lifecycle step is tracked separately via `provisioned`.
export const PROCESS_STEPS: ProcessStep[] = [
  {
    n: 1,
    key: PAGE.ACQUIRE_SOURCE,
    label: "Source Acquisition",
    automation: null,
    desc: "Choose a source path, acquire the snapshot, and manage workspace source files",
  },
  {
    n: 2,
    key: PAGE.METADATA,
    label: "Provide Metadata",
    automation: null,
    desc: "Input project identity metadata",
  },
  {
    n: 3,
    key: PAGE.OBSERVE_HARDWARE,
    label: "Create HBOM",
    automation: null,
    desc: "Enter hardware bill of materials",
  },
  {
    n: 4,
    key: PAGE.EVALUATE_REPRODUCIBILITY,
    label: "Reproducibility Readiness",
    automation: AUTOMATION_BY_KEY[PAGE.EVALUATE_REPRODUCIBILITY],
    desc: "Analyze the source repository",
  },
  {
    n: 5,
    key: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
    label: "Build Experiment Environment",
    automation: AUTOMATION_BY_KEY[PAGE.BUILD_EXPERIMENT_ENVIRONMENT],
    desc: "Build the experiment environment artifact",
  },
  {
    n: 6,
    key: PAGE.GENERATE_SBOM,
    label: "Generate SBOM",
    automation: AUTOMATION_BY_KEY[PAGE.GENERATE_SBOM],
    desc: "Inventory the software in the experiment environment",
  },
  {
    n: 7,
    key: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
    label: "Test Activation",
    automation: AUTOMATION_BY_KEY[PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT],
    desc: "Verify the experiment environment starts and activates",
  },
  {
    n: 8,
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    automation: null,
    desc: "Define reproducibility experiment commands",
  },
  {
    n: 9,
    key: PAGE.ARCHIVE,
    label: "Deposit & Share",
    automation: null,
    desc: "Archive and publish",
  },
  {
    n: 10,
    key: PAGE.SEAL_REE,
    label: "Seal",
    automation: null,
    desc: "Seal the REE",
  },
];

/** The audit step whose receipt speaks for each page, for showing it stale: a page does the step it is keyed by. */
export const EVIDENCE_STEP_BY_PAGE: Readonly<Partial<Record<AppShellPage, EvidenceStep>>> = {
  [PAGE.ACQUIRE_SOURCE]: PAGE.ACQUIRE_SOURCE,
  [PAGE.OBSERVE_HARDWARE]: PAGE.OBSERVE_HARDWARE,
  [PAGE.EVALUATE_REPRODUCIBILITY]: PAGE.EVALUATE_REPRODUCIBILITY,
  [PAGE.BUILD_EXPERIMENT_ENVIRONMENT]: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
  [PAGE.GENERATE_SBOM]: PAGE.GENERATE_SBOM,
  [PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT]: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
};

// Whether a page's step is done is the REE's own word (the document's `steps`, what `ree status` prints), so a
// reload, a second tab or a person at a terminal all see the same thing.
function authoringStepOf(page: AppShellPage): AuthoringStepKey | undefined {
  return AUTHORING_STEP_KEYS.find((key) => key === page);
}

// `badges` is the live outcome of runs started here. Deposits are not steps of
// the REE, so they come from those durable run outcomes.
function hasProcessStepCompleted(stepKey: AppShellPage, ree: ReeEditorViewModel, badges: Badges) {
  const authoringStep = authoringStepOf(stepKey);
  if (authoringStep) return isAuthoringStepComplete(ree.steps, authoringStep);
  if (stepKey === PAGE.ARCHIVE)
    return ["swh", "zenodo", "dataverse"].some((key) => isSuccessfulStepOutcome(badges?.[key]));
  return isSuccessfulStepOutcome(badges?.[stepKey]);
}

export function resolveNavCompleted(
  step: ProcessStep,
  ree: ReeEditorViewModel,
  badges: Badges,
): boolean {
  return step.navCompleted
    ? step.navCompleted(ree, badges)
    : hasProcessStepCompleted(step.key, ree, badges);
}
