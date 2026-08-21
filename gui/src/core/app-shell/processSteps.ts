import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { hbomHasAnyComponents } from "@core/hbom/HbomSummary";
import type { Badges } from "@core/ree/ReeTypes";
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
    key: PAGE.SOURCE,
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
    key: PAGE.HBOM,
    label: "Create HBOM",
    automation: null,
    desc: "Enter hardware bill of materials",
  },
  {
    n: 4,
    key: PAGE.EVALUATE,
    label: "Reproducibility Readiness",
    automation: AUTOMATION_BY_KEY[PAGE.EVALUATE],
    desc: "Analyze the source repository",
  },
  {
    n: 5,
    key: PAGE.BUILD,
    label: "Build Runtime",
    automation: AUTOMATION_BY_KEY[PAGE.BUILD],
    desc: "Build the runtime artifact",
  },
  {
    n: 6,
    key: PAGE.SBOM,
    label: "Generate SBOM",
    automation: AUTOMATION_BY_KEY[PAGE.SBOM],
    desc: "Inventory the software in the runtime",
  },
  {
    n: 7,
    key: PAGE.ACTIVATION,
    label: "Test Activation",
    automation: AUTOMATION_BY_KEY[PAGE.ACTIVATION],
    desc: "Verify the runtime starts and activates",
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
    key: PAGE.SEAL,
    label: "Seal",
    automation: null,
    desc: "Seal the REE",
  },
];

function hasProcessStepCompleted(stepKey: AppShellPage, ree: ReeEditorViewModel, badges: Badges) {
  if (stepKey === PAGE.SOURCE) return !!ree.source.sourceAvailable;
  if (stepKey === PAGE.METADATA) return !!ree.spec.name;
  if (stepKey === PAGE.EXPERIMENTS)
    return (ree.spec.experiments || []).some((entry) => !!entry.name.trim());
  if (stepKey === PAGE.HBOM) return hbomHasAnyComponents(ree.spec.hardwareDescription);
  if (stepKey === PAGE.BUILD) return !!badges?.build;
  if (stepKey === PAGE.SEAL) return !!ree.artifact.sealedAt;
  if (stepKey === PAGE.ARCHIVE) return !!badges?.swh || !!badges?.zenodo || !!badges?.dataverse;
  return !!badges?.[stepKey];
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
