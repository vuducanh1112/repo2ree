import { hbomHasAnyComponents } from "../../../../core/hbom/HbomSummary";
import type { Badges } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../../core/review/axes";
import { Ic } from "../../shared/components/Icon";
import { PROCESS_STEPS, resolveNavCompleted } from "../sidebar/processSteps";
import { type AppShellPage, isRuntimeEnvPage, PAGE } from "../state/pages";

// A canvas node is a page floating around the pod in the hub. `kind` keeps the
// declarations/evidence split: things you DECLARE cluster left, evidence the
// system RETURNS clusters right. `x`/`y` are canvas coordinates with the pod at
// the origin (0,0). `color`/`shadow` drive its cable to the pod.
export interface CanvasNode {
  key: AppShellPage;
  label: string;
  kind: "setup" | "declare" | "evidence" | "files";
  x: number;
  y: number;
  color: string;
  shadow: string;
  icon: (size?: number) => JSX.Element;
}

export const CANVAS_NODES: CanvasNode[] = [
  {
    key: PAGE.WORKBENCH,
    label: "Workbench",
    kind: "setup",
    x: 0,
    y: -236,
    color: "#64748b",
    shadow: "#334155",
    icon: Ic.package,
  },
  {
    key: PAGE.SOURCE,
    label: "Source",
    kind: "declare",
    x: -312,
    y: -150,
    color: "#f59e0b",
    shadow: "#92400e",
    icon: Ic.globe,
  },
  {
    key: PAGE.METADATA,
    label: "Metadata",
    kind: "declare",
    x: -378,
    y: -16,
    color: "#22c55e",
    shadow: "#166534",
    icon: Ic.grid,
  },
  {
    key: PAGE.HBOM,
    label: "Hardware",
    kind: "declare",
    x: -330,
    y: 120,
    color: "#0f766e",
    shadow: "#134e4a",
    icon: Ic.chip,
  },
  {
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    kind: "declare",
    x: -190,
    y: 236,
    color: "#4f46e5",
    shadow: "#3730a3",
    icon: Ic.terminal,
  },
  {
    key: PAGE.EVALUATE,
    label: "Repro Label",
    kind: "evidence",
    x: 312,
    y: -150,
    color: "#7c3aed",
    shadow: "#3b0764",
    icon: Ic.star,
  },
  {
    key: PAGE.BUILD,
    label: "Runtime",
    kind: "evidence",
    x: 378,
    y: -16,
    color: "#0891b2",
    shadow: "#164e63",
    icon: Ic.cpu,
  },
  {
    key: PAGE.ARCHIVE,
    label: "Archive",
    kind: "evidence",
    x: 330,
    y: 120,
    color: "#e4572e",
    shadow: "#7c2d12",
    icon: Ic.archive,
  },
  {
    key: PAGE.SEAL,
    label: "Seal",
    kind: "evidence",
    x: 190,
    y: 236,
    color: "#b91c1c",
    shadow: "#7f1d1d",
    icon: Ic.lock,
  },
  {
    key: PAGE.FILES,
    label: "Files",
    kind: "files",
    x: 0,
    y: 252,
    color: "#64748b",
    shadow: "#334155",
    icon: Ic.files,
  },
];

const STEP_BY_KEY = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

// A node reflects "done" from the same lifecycle source of truth the rail used.
export function isNodeDone(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  badges: Badges,
  provisioned: boolean,
): boolean {
  if (node.key === PAGE.FILES) return !!ree.sourceAvailable;
  const step = STEP_BY_KEY.get(node.key);
  return step ? resolveNavCompleted(step, ree, badges, provisioned) : false;
}

// Until the workbench is provisioned, only the Workbench node is reachable.
export function isNodeLocked(node: CanvasNode, provisioned: boolean): boolean {
  return !provisioned && node.key !== PAGE.WORKBENCH;
}

export function isNodeActive(node: CanvasNode, page: AppShellPage): boolean {
  return page === node.key || (node.key === PAGE.BUILD && isRuntimeEnvPage(page));
}

export function activeNode(page: AppShellPage): CanvasNode | undefined {
  return CANVAS_NODES.find((node) => isNodeActive(node, page));
}

// Readiness = how many lifecycle steps are complete, for the hub readout.
export function lifecycleProgress(
  ree: ReeEditorViewModel,
  badges: Badges,
  provisioned: boolean,
): { completed: number; total: number } {
  const completed = PROCESS_STEPS.filter((step) =>
    resolveNavCompleted(step, ree, badges, provisioned),
  ).length;
  return { completed, total: PROCESS_STEPS.length };
}

export interface SummaryRow {
  label: string;
  value: string | null;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] || url;
  }
}

// Per-node summary, mirroring what the old Overview panels surfaced.
export function nodeSummary(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  provisioned: boolean,
): SummaryRow[] {
  switch (node.key) {
    case PAGE.WORKBENCH:
      return [{ label: "Bench", value: provisioned ? "provisioned" : null }];
    case PAGE.SOURCE:
      return [
        { label: "Origin", value: ree.origin_url ? hostOf(ree.origin_url) : null },
        { label: "Files", value: ree.sourceAvailable ? "in workspace" : null },
      ];
    case PAGE.METADATA:
      return [
        { label: "Name", value: ree.name || null },
        { label: "Version", value: ree.catalog_metadata?.version || null },
      ];
    case PAGE.HBOM:
      return [
        {
          label: "Components",
          value: hbomHasAnyComponents(ree.hardware_description) ? "described" : null,
        },
      ];
    case PAGE.EXPERIMENTS: {
      const count = (ree.experiments ?? []).filter((entry) => entry.command.trim() !== "").length;
      return [{ label: "Commands", value: count > 0 ? `${count} defined` : null }];
    }
    case PAGE.EVALUATE: {
      const scored = ree.dependencyLevel || ree.environmentLevel || ree.machineLevel;
      return [{ label: "Level", value: scored ? standingMeta(ree).short : null }];
    }
    case PAGE.BUILD:
      return [
        {
          label: "Runtime",
          value: ree.runtime && ree.runtime !== "__skipped__" ? "image ready" : null,
        },
        { label: "SBOM", value: ree.sbom ? "inventoried" : null },
      ];
    case PAGE.ARCHIVE:
      return [
        { label: "DOI", value: ree.zenodo_doi || ree.dataverse_doi || null },
        { label: "SWHID", value: ree.swhid ? "assigned" : null },
      ];
    case PAGE.SEAL:
      return [{ label: "State", value: ree.sealedAt ? "sealed" : "draft" }];
    default:
      return [];
  }
}
