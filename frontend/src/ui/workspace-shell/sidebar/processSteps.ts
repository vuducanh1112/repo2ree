import type { AutomationStepDefinition } from "../../../application/workflow/WorkflowStepTypes";
import { AUTOMATION_STEPS } from "../../../application/workflow/workflowCatalog";
import {
  PAGE,
  type WorkspaceShellPage,
} from "../../../application/workspace-shell/WorkspaceShellPages";
import { hbomHasAnyComponents } from "../../../domain/hbom/HbomSummary";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";
import type { Badges } from "../../../domain/ree/ReeTypes";
import { Ic } from "../../shared/components/Icon";

interface ProcessStep {
  n: number;
  key: WorkspaceShellPage;
  label: string;
  IC: (size?: number) => JSX.Element;
  automation: AutomationStepDefinition | null;
  desc: string;
}

const AUTOMATION_BY_KEY: Record<string, AutomationStepDefinition> = Object.fromEntries(
  AUTOMATION_STEPS.map((step) => [step.key, step]),
) as Record<string, AutomationStepDefinition>;

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
    label: "Evaluate",
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
    desc: "Build the runtime tarball",
  },
  {
    n: 6,
    key: PAGE.SBOM,
    label: "Generate SBOM",
    IC: Ic.package,
    automation: AUTOMATION_BY_KEY[PAGE.SBOM],
    desc: "Scan runtime with syft",
  },
  {
    n: 7,
    key: PAGE.ACTIVATION,
    label: "Test Activation",
    IC: Ic.shield,
    automation: AUTOMATION_BY_KEY[PAGE.ACTIVATION],
    desc: "Verify container activates",
  },
  {
    n: 8,
    key: PAGE.ARCHIVE,
    label: "Deposit & Share",
    IC: Ic.globe,
    automation: null,
    desc: "Archive and publish",
  },
  { n: 9, key: PAGE.SEAL, label: "Seal", IC: Ic.lock, automation: null, desc: "Seal the REE" },
];

export function hasProcessStepCompleted(
  stepKey: WorkspaceShellPage,
  ree: ReeDraftViewModel,
  badges: Badges,
) {
  if (stepKey === PAGE.SOURCE) return !!ree._sourceAvailable;
  if (stepKey === PAGE.METADATA) return !!ree.name;
  if (stepKey === PAGE.HBOM) return hbomHasAnyComponents(ree.hardware_description);
  if (stepKey === PAGE.SEAL) return !!ree._sealedAt;
  if (stepKey === PAGE.ARCHIVE) return !!badges?.swh || !!badges?.zenodo || !!badges?.dataverse;
  return !!badges?.[stepKey];
}
