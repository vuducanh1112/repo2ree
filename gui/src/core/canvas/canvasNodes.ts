import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import {
  EVIDENCE_STEP_BY_PAGE,
  PROCESS_STEPS,
  resolveNavCompleted,
} from "@core/app-shell/processSteps";
import { axisStandings, axisStepLabel } from "@core/evaluate/axes";
import type { SbomCrossCheckSummary } from "@core/evaluate/Threat";
import type { ReceiptOperation } from "@core/generated/vocabulary";
import type { ReceiptView } from "@core/receipts/authorReceipts";
import type { Badges } from "@core/ree/ReeTypes";
import { isAuditStale } from "@core/ree/StepEvidence";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { findFileByWorkspacePath } from "@core/workspace/fileTreeTraversal";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";

export type NodeZone = "outer" | "inner" | "core";

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

export const FLOOR_TILT_DEGREES = 54;

export const SCENE_DEPTH = 1900;

const TILT = (FLOOR_TILT_DEGREES * Math.PI) / 180;
const TILT_COS = Math.cos(TILT);
const TILT_SIN = Math.sin(TILT);

export const RING = { rx: 790, ry: 470 } as const;

const CARD_BOX = { width: 248, height: 210 } as const;

const FLOOR_PLATE = { width: 152, height: 96 } as const;

const POD_BOX = { halfWidth: 200, height: 360 } as const;

export interface CanvasNode {
  key: AppShellPage;
  label: string;
  zone: NodeZone;
  angle: number;
  x: number;
  y: number;
  standHeight: number;
  iconKey: CanvasIconKey;
}

type CanvasNodePlacement = Omit<CanvasNode, "x" | "y">;

function ringPosition(angle: number): { x: number; y: number } {
  const radians = (angle * Math.PI) / 180;
  return {
    x: Math.round(RING.rx * Math.sin(radians)),
    y: Math.round(-RING.ry * Math.cos(radians)),
  };
}

const BILLBOARD_CORRECTION = 1;

export function nodeScale(node: CanvasNode): number {
  const perspective = SCENE_DEPTH / (SCENE_DEPTH - node.y * TILT_SIN);
  return (1 / perspective) ** BILLBOARD_CORRECTION;
}

export function screenPointFromFloor(point: { x: number; y: number }): { x: number; y: number } {
  const perspective = SCENE_DEPTH / (SCENE_DEPTH - point.y * TILT_SIN);
  return { x: point.x * perspective, y: point.y * TILT_COS * perspective };
}

export function floorPointFromScreen(point: { x: number; y: number }): { x: number; y: number } {
  const y = (point.y * SCENE_DEPTH) / (TILT_COS * SCENE_DEPTH + point.y * TILT_SIN);
  const perspective = SCENE_DEPTH / (SCENE_DEPTH - y * TILT_SIN);
  return { x: point.x / perspective, y };
}

interface ScreenBox {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export function nodeCardBox(node: CanvasNode): ScreenBox {
  const anchor = screenPointFromFloor(node);
  const bottom = anchor.y - node.standHeight;
  return {
    left: anchor.x - CARD_BOX.width / 2,
    right: anchor.x + CARD_BOX.width / 2,
    top: bottom - CARD_BOX.height,
    bottom,
  };
}

export function nodeScreenBox(node: CanvasNode): ScreenBox {
  const card = nodeCardBox(node);
  const plateNear = screenPointFromFloor({ x: node.x, y: node.y + FLOOR_PLATE.height / 2 });
  const halfWidth = Math.max(CARD_BOX.width, FLOOR_PLATE.width) / 2;
  const anchor = screenPointFromFloor(node);
  return {
    left: anchor.x - halfWidth,
    right: anchor.x + halfWidth,
    top: card.top,
    bottom: plateNear.y,
  };
}

export function canvasWorldBounds(nodes: readonly CanvasNode[] = CANVAS_NODES): {
  left: number;
  top: number;
  width: number;
  height: number;
} {
  let left: number = -POD_BOX.halfWidth;
  let right: number = POD_BOX.halfWidth;
  let top: number = -POD_BOX.height;
  let bottom = 0;
  for (const node of nodes) {
    const box = nodeScreenBox(node);
    left = Math.min(left, box.left);
    right = Math.max(right, box.right);
    top = Math.min(top, box.top);
    bottom = Math.max(bottom, box.bottom);
  }
  return { left, top, width: right - left, height: bottom - top };
}

const CANVAS_NODE_PLACEMENTS: CanvasNodePlacement[] = [
  {
    key: PAGE.ACQUIRE_SOURCE,
    label: "Source",
    zone: "outer",
    angle: 265,
    standHeight: 96,
    iconKey: "globe",
  },
  {
    key: PAGE.METADATA,
    label: "Metadata",
    zone: "outer",
    angle: 314.2,
    standHeight: 150,
    iconKey: "grid",
  },
  {
    key: PAGE.OBSERVE_HARDWARE,
    label: "Hardware",
    zone: "inner",
    angle: 342.4,
    standHeight: 100,
    iconKey: "chip",
  },
  {
    key: PAGE.EVALUATE_REPRODUCIBILITY,
    label: "Reproducibility Readiness",
    zone: "inner",
    angle: 7,
    standHeight: 164,
    iconKey: "star",
  },
  {
    key: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
    label: "Build Experiment Environment",
    zone: "inner",
    angle: 32.8,
    standHeight: 104,
    iconKey: "cpu",
  },
  {
    key: PAGE.GENERATE_SBOM,
    label: "SBOM",
    zone: "inner",
    angle: 68.3,
    standHeight: 168,
    iconKey: "package",
  },
  {
    key: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
    label: "Activation",
    zone: "inner",
    angle: 124.1,
    standHeight: 96,
    iconKey: "shield",
  },
  {
    key: PAGE.EXPERIMENTS,
    label: "Experiments",
    zone: "core",
    angle: 155,
    standHeight: 150,
    iconKey: "terminal",
  },
  {
    key: PAGE.SEAL_REE,
    label: "Seal",
    zone: "outer",
    angle: 180,
    standHeight: 104,
    iconKey: "lock",
  },
  {
    key: PAGE.ARCHIVE,
    label: "Archive",
    zone: "outer",
    angle: 214,
    standHeight: 96,
    iconKey: "archive",
  },
];

export const CANVAS_NODES: CanvasNode[] = CANVAS_NODE_PLACEMENTS.map((placement) => ({
  ...placement,
  ...ringPosition(placement.angle),
}));

const STEP_BY_KEY = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

export function isNodeDone(node: CanvasNode, ree: ReeEditorViewModel, badges: Badges): boolean {
  const step = STEP_BY_KEY.get(node.key);
  return step ? resolveNavCompleted(step, ree, badges) : false;
}

export function isNodeStale(node: CanvasNode, ree: ReeEditorViewModel): boolean {
  const step = EVIDENCE_STEP_BY_PAGE[node.key];
  return step ? isAuditStale(ree.audit, step) : false;
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
  title?: string;
}

export interface CanvasScriptPreview {
  key: string;
  label: string;
  path: string;
  lines: readonly string[];
  available: boolean;
}

export interface CanvasReceiptSummary {
  count: number;
  label: string;
  duration: string;
  recordedAt: string;
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
  buildExperimentEnvironmentScriptPath?: string;
  activateExperimentEnvironmentScriptPath?: string;
  crossCheck?: SbomCrossCheckSummary | null;
}

function hostOf(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url.replace(/^https?:\/\//, "").split("/")[0] || url;
  }
}

function abbreviate(value: string): string {
  return value.length > 20 ? `${value.slice(0, 16)}…` : value;
}

function basename(path: string): string {
  return path.split("/").at(-1) || path;
}

export function nodeSummary(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
  context: CanvasNodeOverviewContext = {},
): SummaryRow[] {
  switch (node.key) {
    case PAGE.ACQUIRE_SOURCE: {
      const repo = ree.source.sourceAvailable ? sourceRepo : undefined;
      return [
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
        { label: "Description", value: ree.spec.catalogMetadata?.description || null },
        { label: "Version", value: ree.spec.catalogMetadata?.version || null },
        { label: "Website", value: ree.spec.catalogMetadata?.website || null },
        {
          label: "Keywords",
          value: ree.spec.catalogMetadata?.keywords.length
            ? ree.spec.catalogMetadata.keywords.join(", ")
            : null,
        },
        {
          label: "Contributors",
          value: ree.spec.catalogMetadata?.contributors.length
            ? ree.spec.catalogMetadata.contributors
                .map((contributor) => contributor.name || contributor.identifier)
                .join(", ")
            : null,
        },
        {
          label: "Corresponding author",
          value: ree.spec.catalogMetadata?.correspondingAuthorIdentifier || null,
        },
      ];
    case PAGE.OBSERVE_HARDWARE: {
      const hbom = ree.spec.hbom;
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
      const storage = Object.values(hbom.storage).reduce(
        (total, item) => total + item.quantity * item.capacityGb,
        0,
      );
      const network = Object.values(hbom.network).reduce(
        (total, item) => total + item.quantity * item.bandwidthGbps,
        0,
      );
      return [
        {
          label: "Compute",
          value: cpus ? `${cpus} CPU · ${cores} cores` : null,
        },
        { label: "Memory", value: memory ? `${memory} GB` : null },
        { label: "GPU", value: gpus ? String(gpus) : null },
        { label: "Storage", value: storage ? `${storage} GB` : null },
        { label: "Network", value: network ? `${network} Gbps` : null },
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
    case PAGE.EVALUATE_REPRODUCIBILITY:
      return [
        ...axisStandings(ree.evaluation).map(({ axis, level }) => ({
          label: axis.label,
          value: axisStepLabel(axis, level),
        })),
        {
          label: "Detected deps",
          value: ree.evaluation.detectedDependencies || null,
        },
      ];
    case PAGE.BUILD_EXPERIMENT_ENVIRONMENT:
      return [
        {
          label: "Experiment environment",
          value:
            ree.spec.experimentEnvironmentPath &&
            ree.spec.experimentEnvironmentPath !== "__skipped__"
              ? "image ready"
              : null,
        },
      ];
    case PAGE.GENERATE_SBOM: {
      const sbom = ree.spec.sbom || "";
      const crossCheck = context.crossCheck;
      return [
        {
          label: "SBOM",
          value: sbom ? abbreviate(basename(sbom)) : null,
          title: sbom || undefined,
        },
        {
          label: "Cross-check",
          value: crossCheck
            ? `${crossCheck.observedMatched}/${crossCheck.observedTotal} matched`
            : null,
        },
      ];
    }
    case PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT:
      return [
        {
          label: "Runs",
          value: context.activateExperimentEnvironmentScriptPath ? "alone" : null,
          title: "The activate experiment environment script, around a command that does nothing",
        },
      ];
    case PAGE.ARCHIVE:
      return [
        { label: "DOI", value: null },
        { label: "SWHID", value: ree.spec.swhid || null, title: ree.spec.swhid },
      ];
    case PAGE.SEAL_REE: {
      const hash = ree.artifact.sealHash || "";
      return [
        { label: "State", value: ree.artifact.sealedAt ? "sealed" : "draft" },
        { label: "Hash", value: hash ? abbreviate(hash) : null, title: hash || undefined },
      ];
    }
    default:
      return [];
  }
}

const RECEIPT_OPERATIONS_BY_PAGE: Readonly<
  Partial<Record<AppShellPage, readonly ReceiptOperation[]>>
> = {
  [PAGE.ACQUIRE_SOURCE]: ["acquire_source"],
  [PAGE.OBSERVE_HARDWARE]: ["observe_hardware"],
  [PAGE.EVALUATE_REPRODUCIBILITY]: ["evaluate_reproducibility"],
  [PAGE.BUILD_EXPERIMENT_ENVIRONMENT]: ["build_experiment_environment"],
  [PAGE.GENERATE_SBOM]: ["generate_sbom", "cross_check_sbom"],
  [PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT]: ["activate_experiment_environment"],
  [PAGE.EXPERIMENTS]: ["run_experiment"],
};

function receiptField(receipt: ReceiptView, key: string): string {
  return receipt.fields.find((field) => field.key === key)?.value ?? "";
}

function scriptDigest(node: CanvasNode, receipt: ReceiptView): string {
  if (node.key === PAGE.BUILD_EXPERIMENT_ENVIRONMENT)
    return receiptField(receipt, "build_experiment_environment_script_digest");
  if (node.key === PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT || node.key === PAGE.EXPERIMENTS) {
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

export function nodeOverview(
  node: CanvasNode,
  ree: ReeEditorViewModel,
  sourceRepo?: SourceRepoMetadata,
  context: CanvasNodeOverviewContext = {},
): CanvasNodeOverview {
  const files = context.workspaceFiles ?? [];
  const experiments = ree.spec.experiments ?? [];
  let scripts: CanvasScriptPreview[] = [];

  if (node.key === PAGE.BUILD_EXPERIMENT_ENVIRONMENT) {
    scripts = [
      scriptPreview(
        files,
        "build_experiment_environment",
        "BUILD SCRIPT",
        context.buildExperimentEnvironmentScriptPath,
        3,
      ),
    ];
  } else if (node.key === PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT) {
    scripts = [
      scriptPreview(
        files,
        "activate_experiment_environment",
        "ACTIVATE SCRIPT",
        context.activateExperimentEnvironmentScriptPath,
        3,
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
    facts: nodeSummary(node, ree, sourceRepo, context),
    scripts,
    evidenceExpected: !!RECEIPT_OPERATIONS_BY_PAGE[node.key]?.length,
    receipt: receiptSummary(node, context.receipts ?? [], experiments.length),
  };
}
