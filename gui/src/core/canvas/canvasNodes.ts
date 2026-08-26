import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import { axisStandings, axisStepLabel } from "@core/evaluate/axes";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { findFileByWorkspacePath } from "@core/workspace/fileTreeTraversal";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";

// A canvas node is a page floating around the pod in the hub. `kind` keeps the
// declarations/evidence split: things you DECLARE cluster left, evidence the
// system RETURNS clusters right. `x`/`y` are canvas coordinates with the pod at
// the origin (0,0). How a node and its cable read is keyed off `key` in the
// shell (see theme/tones.css), so the node carries no colour of its own.
// `zone` groups nodes into concentric shells around the pod for the master
// view: `core` is the experiment itself, `inner` the execution substrate it
// runs on, `outer` the provenance/credential membrane around the whole thing.
export type NodeZone = "outer" | "inner" | "core";

/**
 * Which glyph a node shows, named rather than supplied. The node definitions are
 * functional-core data, so they carry the *key* and the shell resolves it to a
 * component — the same indirection `ReeStepIconKey` and `stepIcons.tsx` already
 * use for the pipeline steps.
 */
export type CanvasIconKey =
  | "globe"
  | "grid"
  | "chip"
  | "terminal"
  | "star"
  | "cpu"
  | "package"
  | "shield"
  | "archive"
  | "lock";

export interface CanvasNode {
  key: AppShellPage;
  label: string;
  kind: "setup" | "declare" | "evidence";
  zone: NodeZone;
  x: number;
  y: number;
  /** Height of the billboard's support above the 2.5D bench, in world units. */
  standHeight: number;
  iconKey: CanvasIconKey;
}

// The Workbench is absent from the ring on purpose: it IS the canvas — the lab
// the pod sits in. Its setup lives in WorkbenchLab (pre-provision) and the
// bench nameplate on the hub (post-provision).
export const CANVAS_NODES: CanvasNode[] = [
  {
    key: PAGE.SOURCE,
    label: "Source",
    kind: "declare",
    zone: "outer",
    x: -560,
    y: -340,
    standHeight: 175,
    iconKey: "globe",
  },
  {
    key: PAGE.METADATA,
    label: "Metadata",
    kind: "declare",
    zone: "outer",
    x: -712,
    y: -60,
    standHeight: 152,
    iconKey: "grid",
  },
  {
    key: PAGE.HBOM,
    label: "Hardware",
    kind: "declare",
    zone: "inner",
    x: -622,
    y: 200,
    standHeight: 105,
    iconKey: "chip",
  },
  {
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    kind: "declare",
    zone: "core",
    x: -288,
    y: 430,
    standHeight: 128,
    iconKey: "terminal",
  },
  {
    key: PAGE.EVALUATE,
    label: "Reproducibility Readiness",
    kind: "evidence",
    zone: "inner",
    x: 560,
    y: -340,
    standHeight: 175,
    iconKey: "star",
  },
  // Build / SBOM / Activation are the three facets of the runtime — the inner
  // shell. They are plain inner-shell members (each cables to the inner shell),
  // not a node-to-node chain. Direction is read from their layout: Build sits at
  // the inlet (nearest the pod / the source-facing side), and SBOM + Activation
  // sit downstream toward the core, since they consume the artifact Build emits.
  {
    key: PAGE.BUILD,
    label: "Build",
    kind: "evidence",
    zone: "inner",
    x: 560,
    y: 30,
    standHeight: 118,
    iconKey: "cpu",
  },
  {
    key: PAGE.SBOM,
    label: "SBOM",
    kind: "evidence",
    zone: "inner",
    x: 880,
    y: -240,
    standHeight: 130,
    iconKey: "package",
  },
  {
    key: PAGE.ACTIVATION,
    label: "Activation",
    kind: "evidence",
    zone: "inner",
    x: 796,
    y: 250,
    standHeight: 97,
    iconKey: "shield",
  },
  {
    key: PAGE.ARCHIVE,
    label: "Archive",
    kind: "evidence",
    zone: "outer",
    x: 556,
    y: 420,
    standHeight: 84,
    iconKey: "archive",
  },
  {
    key: PAGE.SEAL,
    label: "Seal",
    kind: "evidence",
    zone: "outer",
    x: 250,
    y: 480,
    standHeight: 95,
    iconKey: "lock",
  },
];

const STEP_BY_KEY = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

// A node reflects "done" from the same lifecycle source of truth the rail used.
export function isNodeDone(node: CanvasNode, ree: ReeEditorViewModel, badges: Badges): boolean {
  const step = STEP_BY_KEY.get(node.key);
  return step ? resolveNavCompleted(step, ree, badges) : false;
}

// Every node lives inside the workbench, so nothing on the ring is reachable
// until the workbench (the lab) is provisioned.
export function isNodeLocked(_node: CanvasNode, provisioned: boolean): boolean {
  return !provisioned;
}

export function isNodeActive(node: CanvasNode, page: AppShellPage): boolean {
  return page === node.key;
}

export function activeNode(page: AppShellPage): CanvasNode | undefined {
  return CANVAS_NODES.find((node) => isNodeActive(node, page));
}

export interface SummaryRow {
  label: string;
  value: string | null;
  /** Full text shown on hover when `value` is a shortened form. */
  title?: string;
}

export interface CanvasScriptPreview {
  key: string;
  label: string;
  path: string;
  /** A deliberately short, exact preview of the saved workspace file. */
  lines: readonly string[];
  available: boolean;
}

export interface CanvasReceiptSummary {
  count: number;
  label: string;
  duration: string;
  recordedAt: string;
  /** Script digest recorded by the operation, already abbreviated for display. */
  scriptDigest: string;
}

export interface CanvasNodeOverview {
  facts: SummaryRow[];
  scripts: CanvasScriptPreview[];
  evidenceExpected: boolean;
  receipt: CanvasReceiptSummary | null;
}

interface CanvasNodeOverviewContext {
  workspaceFiles?: FileTreeNode[];
  receipts?: ReceiptView[];
  /** Backend-owned reserved path published by the script-template catalog. */
  buildScriptPath?: string;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] || url;
  }
}

// Per-node summary: the headline facts a node shows before the user dives in.
export function nodeSummary(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
): SummaryRow[] {
  switch (node.key) {
    case PAGE.SOURCE: {
      // Once a source is in the workspace, surface the backend-computed stats;
      // before that, fall back to the declared origin so the card isn't empty.
      const repo = ree.source.sourceAvailable ? sourceRepo : undefined;
      return [
        { label: "Name", value: repo?.name ?? null },
        { label: "Size", value: repo?.sizeLabel ?? null },
        {
          label: "Origin",
          value: repo
            ? hostOf(repo.origin)
            : ree.spec.originUrl
              ? hostOf(ree.spec.originUrl)
              : null,
        },
        { label: "SWHID", value: repo?.swhid || null, title: repo?.swhid },
      ];
    }
    case PAGE.METADATA:
      return [
        { label: "Name", value: ree.spec.name || null },
        { label: "Version", value: ree.spec.catalogMetadata?.version || null },
        {
          label: "Contributors",
          value: ree.spec.catalogMetadata?.contributors.length
            ? String(ree.spec.catalogMetadata.contributors.length)
            : null,
        },
      ];
    case PAGE.HBOM: {
      const hbom = ree.spec.hardwareDescription;
      const cpus = Object.values(hbom.cpus).reduce((total, cpu) => total + cpu.quantity, 0);
      const cores = Object.values(hbom.cpus).reduce(
        (total, cpu) => total + cpu.quantity * cpu.coresPerCpu,
        0,
      );
      const memory = Object.values(hbom.memory).reduce(
        (total, item) => total + item.quantity * item.capacityGb,
        0,
      );
      const gpus = Object.values(hbom.gpus).reduce((total, gpu) => total + gpu.quantity, 0);
      return [
        {
          label: "Compute",
          value: cpus ? `${cpus} CPU · ${cores} cores` : null,
        },
        { label: "Memory", value: memory ? `${memory} GB` : null },
        { label: "GPU", value: gpus ? String(gpus) : null },
      ];
    }
    case PAGE.EXPERIMENTS: {
      const experiments = ree.spec.experiments ?? [];
      const count = experiments.filter((entry) => entry.runScript?.trim()).length;
      const verifyCount = experiments.filter((entry) => entry.verifyScript?.trim()).length;
      return [
        { label: "Experiments", value: experiments.length ? String(experiments.length) : null },
        { label: "Run scripts", value: count > 0 ? `${count} defined` : null },
        { label: "Verify", value: verifyCount > 0 ? `${verifyCount} defined` : null },
      ];
    }
    case PAGE.EVALUATE:
      // Always surface each axis's standing — level 0 reads as "None", so the
      // three axes are visible whether or not the REE has been scored yet.
      return axisStandings(ree.evaluation).map(({ axis, level }) => ({
        label: axis.label,
        value: axisStepLabel(axis, level),
      }));
    case PAGE.BUILD:
      return [
        {
          label: "Runtime",
          value: ree.spec.runtime && ree.spec.runtime !== "__skipped__" ? "image ready" : null,
        },
      ];
    case PAGE.SBOM:
      return [{ label: "SBOM", value: ree.spec.sbom ? "inventoried" : null }];
    case PAGE.ACTIVATION:
      return [
        {
          label: "Run",
          value: ree.spec.activation?.runScript?.trim() ? "configured" : null,
        },
        {
          label: "Verify",
          value: ree.spec.activation?.verifyScript?.trim() ? "configured" : null,
        },
      ];
    case PAGE.ARCHIVE:
      return [
        { label: "DOI", value: null },
        { label: "SWHID", value: ree.spec.swhid || null, title: ree.spec.swhid },
      ];
    case PAGE.SEAL:
      return [{ label: "State", value: ree.artifact.sealedAt ? "sealed" : "draft" }];
    default:
      return [];
  }
}

const RECEIPT_OPERATIONS_BY_PAGE: Readonly<Partial<Record<AppShellPage, readonly string[]>>> = {
  [PAGE.SOURCE]: ["acquire_source"],
  [PAGE.HBOM]: ["observe_hardware"],
  [PAGE.EVALUATE]: ["evaluate_reproducibility"],
  [PAGE.BUILD]: ["build_runtime"],
  [PAGE.SBOM]: ["generate_sbom", "cross_check_sbom"],
  // Keep the old spelling readable for REEs written before the contract name settled.
  [PAGE.ACTIVATION]: ["test_activation", "activation_test"],
  [PAGE.EXPERIMENTS]: ["run_experiment"],
};

function receiptField(receipt: ReceiptView, key: string): string {
  return receipt.fields.find((field) => field.key === key)?.value ?? "";
}

function scriptDigest(node: CanvasNode, receipt: ReceiptView): string {
  if (node.key === PAGE.BUILD) return receiptField(receipt, "build_runtime_script_digest");
  if (node.key === PAGE.ACTIVATION || node.key === PAGE.EXPERIMENTS) {
    return receiptField(receipt, "run_script_digest");
  }
  return "";
}

function receiptSummary(
  node: CanvasNode,
  receipts: readonly ReceiptView[],
  experimentCount: number,
): CanvasReceiptSummary | null {
  const operations = RECEIPT_OPERATIONS_BY_PAGE[node.key] ?? [];
  const matching = receipts.filter((receipt) => operations.includes(receipt.operation));
  if (!matching.length) return null;
  const latest = [...matching].sort((left, right) =>
    right.recordedAt.localeCompare(left.recordedAt),
  )[0];
  const label =
    node.key === PAGE.EXPERIMENTS && experimentCount > 0
      ? `${matching.length}/${experimentCount} receipts`
      : matching.length === 1
        ? "receipt recorded"
        : `${matching.length} receipts`;
  return {
    count: matching.length,
    label,
    duration: latest.duration,
    recordedAt: latest.recordedAt,
    scriptDigest: scriptDigest(node, latest),
  };
}

function previewLines(content: string | undefined, limit: number): readonly string[] {
  if (!content?.trim()) return [];
  return content.replace(/\r\n/g, "\n").trimEnd().split("\n").slice(0, limit);
}

function scriptPreview(
  files: FileTreeNode[],
  key: string,
  label: string,
  path: string | null | undefined,
  lineLimit: number,
): CanvasScriptPreview {
  const settledPath = path?.trim() ?? "";
  const file = settledPath ? findFileByWorkspacePath(files, settledPath) : null;
  return {
    key,
    label,
    path: settledPath,
    lines: previewLines(file?.content, lineLimit),
    available: !!file?.content?.trim(),
  };
}

/**
 * The canvas projection of a page: saved inputs plus the materialised evidence
 * those exact inputs produced. It stays read-only; editing remains in the drawer.
 */
export function nodeOverview(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
  context: CanvasNodeOverviewContext = {},
): CanvasNodeOverview {
  const files = context.workspaceFiles ?? [];
  const experiments = ree.spec.experiments ?? [];
  let scripts: CanvasScriptPreview[] = [];

  if (node.key === PAGE.BUILD) {
    scripts = [scriptPreview(files, "build", "BUILD SCRIPT", context.buildScriptPath, 3)];
  } else if (node.key === PAGE.ACTIVATION) {
    scripts = [
      scriptPreview(files, "activation-run", "RUN SCRIPT", ree.spec.activation.runScript, 2),
      scriptPreview(
        files,
        "activation-verify",
        "VERIFY SCRIPT",
        ree.spec.activation.verifyScript,
        1,
      ),
    ];
  } else if (node.key === PAGE.EXPERIMENTS) {
    scripts = experiments.map((experiment, index) =>
      scriptPreview(
        files,
        `experiment-${index}`,
        experiment.name.trim() || `EXPERIMENT ${index + 1}`,
        experiment.runScript,
        1,
      ),
    );
  }

  return {
    facts: nodeSummary(node, ree, sourceRepo),
    scripts,
    evidenceExpected: !!RECEIPT_OPERATIONS_BY_PAGE[node.key]?.length,
    receipt: receiptSummary(node, context.receipts ?? [], experiments.length),
  };
}
