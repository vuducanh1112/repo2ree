import type { ReeSpec } from "../../core/ree/ReeSpec";
import type { FileTreeNode } from "../../core/workspace/FileTree";
import { normalizeSnapshotArchiveName } from "../../core/workspace/PathUtils";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";

type SourceExecutionStatus = "failed" | "canceled";

interface SourceActionPlanSuccess<T> {
  ok: true;
  value: T;
}

interface SourceActionPlanFailure {
  ok: false;
  error: string;
}

type SourceActionPlanResult<T> = SourceActionPlanSuccess<T> | SourceActionPlanFailure;

interface SourceExecutionRequestPlan {
  resetRequest: Record<string, string | boolean | number | null | undefined>;
  runParams: Record<string, string | boolean | number | null | undefined>;
}

interface SourceSnapshotPlan {
  snapshotArchiveName: string;
  sourceAvailable: boolean;
}

interface DownloadSourceSuccessPlan extends SourceSnapshotPlan {
  reeSpecPatch: Partial<ReeSpec>;
  workspaceSourceStatePatch: Partial<WorkspaceSourceState>;
  successMessage: string;
}

interface UploadSourceSuccessPlan extends SourceSnapshotPlan {
  reeSpecPatch: Partial<ReeSpec>;
  workspaceSourceStatePatch: Partial<WorkspaceSourceState>;
  successMessage: string;
}

interface SourceStatePlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  snapshotFiles: FileTreeNode[];
  snapshotArchiveName: string;
  reeSpecPatch: Partial<ReeSpec>;
  workspaceSourceStatePatch: Partial<WorkspaceSourceState>;
  successMessage: string;
}

interface ClearedSourceStatePlan {
  reeSpecPatch: Partial<ReeSpec>;
  workspaceSourceStatePatch: Partial<WorkspaceSourceState>;
  snapshotFiles: FileTreeNode[];
  snapshotArchiveName: string;
  infoMessage: string;
}

function cloneTree(nodes: FileTreeNode[]): FileTreeNode[] {
  return nodes.map((node) => ({
    ...node,
    children: node.children ? cloneTree(node.children) : undefined,
  }));
}

function snapshotArchiveNameFromSourceUrl(sourceUrl: string): string {
  const repoBase =
    (sourceUrl.split("/").filter(Boolean).pop() || "source").replace(
      /\.(git|tar\.gz|tgz|zip)$/i,
      "",
    ) || "source";

  return normalizeSnapshotArchiveName(`${repoBase}-original.tar.gz`);
}

function validateSourceDownload(
  ree: ReeEditorViewModel,
  originType: ReeEditorViewModel["source_type"],
  sourceUrl: string,
): SourceActionPlanResult<{ normalizedSourceUrl: string }> {
  if (ree.sourceAvailable && ree.sourceAcquiredBy === "upload") {
    return {
      ok: false,
      error: "Source already provided via tarball upload. Change source to switch method.",
    };
  }

  const normalizedSourceUrl = sourceUrl.trim();
  if (!normalizedSourceUrl || !originType) {
    return { ok: false, error: "Set origin URL and origin type first" };
  }

  return {
    ok: true,
    value: { normalizedSourceUrl },
  };
}

function validateSourceUpload(
  ree: ReeEditorViewModel,
): SourceActionPlanResult<Record<string, never>> {
  if (ree.sourceAvailable && ree.sourceAcquiredBy === "download") {
    return {
      ok: false,
      error: "Source already provided via origin download. Change source to switch method.",
    };
  }

  return { ok: true, value: {} };
}

function buildSourceExecutionRequestPlan(
  request: Record<string, string | boolean | number | null | undefined>,
): SourceExecutionRequestPlan {
  return {
    resetRequest: request,
    runParams: request,
  };
}

function buildDownloadedSourceSuccess(args: {
  originType: ReeEditorViewModel["source_type"];
  normalizedSourceUrl: string;
  workspaceFiles: FileTreeNode[];
  timestamp: string;
}): DownloadSourceSuccessPlan {
  const snapshotArchiveName = snapshotArchiveNameFromSourceUrl(args.normalizedSourceUrl);
  const sourceAvailable = args.workspaceFiles.length > 0;

  return {
    snapshotArchiveName,
    sourceAvailable,
    reeSpecPatch: {
      origin_url: args.normalizedSourceUrl,
      source_type: args.originType,
    },
    workspaceSourceStatePatch: {
      sourceAvailable,
      sourceAcquiredBy: "download",
      uploadedArchive: "",
      sourceSnapshotArchive: snapshotArchiveName,
      sourceSnapshotCapturedAt: args.timestamp,
    },
    successMessage:
      args.originType === "tarball"
        ? "Tarball downloaded and extracted into workspace"
        : "Source files downloaded into workspace",
  };
}

function buildUploadedSourceSuccess(args: {
  archiveName: string;
  workspaceFiles: FileTreeNode[];
  timestamp: string;
}): UploadSourceSuccessPlan {
  const snapshotArchiveName = normalizeSnapshotArchiveName(args.archiveName);
  const sourceAvailable = args.workspaceFiles.length > 0;

  return {
    snapshotArchiveName,
    sourceAvailable,
    reeSpecPatch: {
      origin_url: "",
      source_type: "",
    },
    workspaceSourceStatePatch: {
      sourceIncluded: true,
      uploadedArchive: args.archiveName,
      sourceAvailable,
      sourceAcquiredBy: "upload",
      sourceSnapshotArchive: snapshotArchiveName,
      sourceSnapshotCapturedAt: args.timestamp,
    },
    successMessage: "Archive extracted into workspace",
  };
}

export function planSourceDownloadAction(
  ree: ReeEditorViewModel,
  originType: ReeEditorViewModel["source_type"],
  sourceUrl: string,
): SourceActionPlanResult<
  SourceExecutionRequestPlan & {
    normalizedSourceUrl: string;
  }
> {
  const plan = validateSourceDownload(ree, originType, sourceUrl);
  if (!plan.ok) {
    return plan;
  }

  return {
    ok: true,
    value: {
      normalizedSourceUrl: plan.value.normalizedSourceUrl,
      ...buildSourceExecutionRequestPlan({
        mode: "download",
        source: plan.value.normalizedSourceUrl,
        sourceType: originType,
      }),
    },
  };
}

export function planSourceUploadAction(
  ree: ReeEditorViewModel,
  archiveName: string,
  archiveContentBase64?: string,
): SourceActionPlanResult<
  SourceExecutionRequestPlan & {
    archiveName: string;
  }
> {
  const plan = validateSourceUpload(ree);
  if (!plan.ok) {
    return plan;
  }

  return {
    ok: true,
    value: {
      archiveName,
      ...buildSourceExecutionRequestPlan({
        mode: "upload",
        archiveName,
        archiveContentBase64,
      }),
    },
  };
}

export function planSourceExecutionFailure(status: SourceExecutionStatus): SourceActionPlanFailure {
  return {
    ok: false,
    error: `Source ${status}`,
  };
}

export function planDownloadedSourceState(args: {
  originType: ReeEditorViewModel["source_type"];
  normalizedSourceUrl: string;
  workspaceFiles: FileTreeNode[];
  timestamp: string;
}): SourceStatePlan {
  const successPlan = buildDownloadedSourceSuccess(args);

  return {
    actionState: "done",
    badge: true,
    timestamp: args.timestamp,
    snapshotFiles: cloneTree(args.workspaceFiles),
    snapshotArchiveName: successPlan.snapshotArchiveName,
    reeSpecPatch: successPlan.reeSpecPatch,
    workspaceSourceStatePatch: successPlan.workspaceSourceStatePatch,
    successMessage: successPlan.successMessage,
  };
}

export function planUploadedSourceState(args: {
  archiveName: string;
  workspaceFiles: FileTreeNode[];
  timestamp: string;
}): SourceStatePlan {
  const successPlan = buildUploadedSourceSuccess(args);

  return {
    actionState: "done",
    badge: true,
    timestamp: args.timestamp,
    snapshotFiles: cloneTree(args.workspaceFiles),
    snapshotArchiveName: successPlan.snapshotArchiveName,
    reeSpecPatch: successPlan.reeSpecPatch,
    workspaceSourceStatePatch: successPlan.workspaceSourceStatePatch,
    successMessage: successPlan.successMessage,
  };
}

export function planClearedSourceStateResult(): ClearedSourceStatePlan {
  return {
    reeSpecPatch: {
      origin_url: "",
    },
    workspaceSourceStatePatch: {
      sourceAvailable: false,
      sourceAcquiredBy: undefined,
      uploadedArchive: "",
      sourceSnapshotArchive: "",
      sourceSnapshotCapturedAt: "",
    },
    snapshotFiles: [],
    snapshotArchiveName: "",
    infoMessage: "Source files removed from workspace — choose download or upload again",
  };
}
