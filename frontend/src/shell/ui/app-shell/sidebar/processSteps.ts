import { hbomHasAnyComponents } from "@core/hbom/HbomSummary";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import type { ReeStepDefinition } from "@core/ree-steps/stepTypes";
import { Ic } from "../../shared/components/Icon";
import { type AppShellPage, PAGE } from "../state/pages";

interface ProcessStep {
  n: number;
  key: AppShellPage;
  label: string;
  IC: (size?: number) => JSX.Element;
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
    IC: Ic.globe,
    automation: null,
    desc: "Choose a source path, acquire the snapshot, and manage workspace source files",
  },
  {
    n: 2,
    key: PAGE.METADATA,
    label: "Provide Metadata",
    IC: Ic.grid,
    automation: null,
    desc: "Input project identity metadata",
  },
  {
    n: 3,
    key: PAGE.HBOM,
    label: "Create HBOM",
    IC: Ic.chip,
    automation: null,
    desc: "Enter hardware bill of materials",
  },
  {
    n: 4,
    key: PAGE.EVALUATE,
    label: "Reproducibility Readiness",
    IC: Ic.star,
    automation: AUTOMATION_BY_KEY[PAGE.EVALUATE],
    desc: "Score reproducibility level",
  },
  {
    n: 5,
    key: PAGE.BUILD,
    label: "Build Runtime",
    IC: Ic.cpu,
    automation: AUTOMATION_BY_KEY[PAGE.BUILD],
    desc: "Build the runtime artifact",
  },
  {
    n: 6,
    key: PAGE.SBOM,
    label: "Generate SBOM",
    IC: Ic.package,
    automation: AUTOMATION_BY_KEY[PAGE.SBOM],
    desc: "Inventory the software in the runtime",
  },
  {
    n: 7,
    key: PAGE.ACTIVATION,
    label: "Test Activation",
    IC: Ic.shield,
    automation: AUTOMATION_BY_KEY[PAGE.ACTIVATION],
    desc: "Verify the runtime starts and activates",
  },
  {
    n: 8,
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    IC: Ic.terminal,
    automation: null,
    desc: "Define reproducibility experiment commands",
  },
  {
    n: 9,
    key: PAGE.ARCHIVE,
    label: "Deposit & Share",
    IC: Ic.globe,
    automation: null,
    desc: "Archive and publish",
  },
  {
    n: 10,
    key: PAGE.SEAL,
    label: "Seal",
    IC: Ic.lock,
    automation: null,
    desc: "Seal the REE",
  },
];

function hasProcessStepCompleted(stepKey: AppShellPage, ree: ReeEditorViewModel, badges: Badges) {
  if (stepKey === PAGE.SOURCE) return !!ree.sourceAvailable;
  if (stepKey === PAGE.METADATA) return !!ree.name;
  if (stepKey === PAGE.EXPERIMENTS)
    return (ree.experiments || []).some((entry) => !!entry.name.trim());
  if (stepKey === PAGE.HBOM) return hbomHasAnyComponents(ree.hardwareDescription);
  if (stepKey === PAGE.BUILD) return !!badges?.build;
  if (stepKey === PAGE.SEAL) return !!ree.sealedAt;
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
