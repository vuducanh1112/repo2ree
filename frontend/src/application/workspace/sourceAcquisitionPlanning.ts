import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { normalizeSnapshotArchiveName } from "../../domain/workspace/PathUtils";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";

type SourceWorkflowStatus = "failed" | "canceled";

interface SourceActionPlanSuccess<T> {
  ok: true;
  value: T;
}

interface SourceActionPlanFailure {
  ok: false;
  error: string;
}

type SourceActionPlanResult<T> = SourceActionPlanSuccess<T> | SourceActionPlanFailure;

interface SourceWorkflowRequestPlan {
  resetRequest: Record<string, string | boolean | number | null | undefined>;
  runParams: Record<string, string | boolean | number | null | undefined>;
}

interface SourceSnapshotPlan {
  snapshotArchiveName: string;
  sourceAvailable: boolean;
}

interface DownloadSourceSuccessPlan extends SourceSnapshotPlan {
  ree: ReeEditorViewModel;
  successMessage: string;
}

interface UploadSourceSuccessPlan extends SourceSnapshotPlan {
  ree: ReeEditorViewModel;
  successMessage: string;
}

interface SourceStatePlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  snapshotFiles: FileTreeNode[];
  snapshotArchiveName: string;
  reePatch: Partial<ReeEditorViewModel>;
  successMessage: string;
}

interface ClearedSourceStatePlan {
  reePatch: Partial<ReeEditorViewModel>;
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

function buildSourceWorkflowRequestPlan(
  request: Record<string, string | boolean | number | null | undefined>,
): SourceWorkflowRequestPlan {
  return {
    resetRequest: request,
    runParams: request,
  };
}

function buildDownloadedSourceSuccess(args: {
  ree: ReeEditorViewModel;
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
    ree: {
      ...args.ree,
      origin_url: args.normalizedSourceUrl,
      source_type: args.originType,
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
  ree: ReeEditorViewModel;
  archiveName: string;
  workspaceFiles: FileTreeNode[];
  timestamp: string;
}): UploadSourceSuccessPlan {
  const snapshotArchiveName = normalizeSnapshotArchiveName(args.archiveName);
  const sourceAvailable = args.workspaceFiles.length > 0;

  return {
    snapshotArchiveName,
    sourceAvailable,
    ree: {
      ...args.ree,
      origin_url: "",
      sourceIncluded: true,
      uploadedArchive: args.archiveName,
      source_type: "",
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
  SourceWorkflowRequestPlan & {
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
      ...buildSourceWorkflowRequestPlan({
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
  SourceWorkflowRequestPlan & {
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
      ...buildSourceWorkflowRequestPlan({
        mode: "upload",
        archiveName,
        archiveContentBase64,
      }),
    },
  };
}

export function planSourceWorkflowFailure(status: SourceWorkflowStatus): SourceActionPlanFailure {
  return {
    ok: false,
    error: `Source ${status}`,
  };
}

export function planDownloadedSourceState(args: {
  ree: ReeEditorViewModel;
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
    reePatch: {
      origin_url: successPlan.ree.origin_url,
      source_type: successPlan.ree.source_type,
      sourceAvailable: successPlan.ree.sourceAvailable,
      sourceAcquiredBy: successPlan.ree.sourceAcquiredBy,
      uploadedArchive: successPlan.ree.uploadedArchive,
      sourceSnapshotArchive: successPlan.ree.sourceSnapshotArchive,
      sourceSnapshotCapturedAt: successPlan.ree.sourceSnapshotCapturedAt,
    },
    successMessage: successPlan.successMessage,
  };
}

export function planUploadedSourceState(args: {
  ree: ReeEditorViewModel;
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
    reePatch: {
      origin_url: successPlan.ree.origin_url,
      sourceIncluded: successPlan.ree.sourceIncluded,
      uploadedArchive: successPlan.ree.uploadedArchive,
      source_type: successPlan.ree.source_type,
      sourceAvailable: successPlan.ree.sourceAvailable,
      sourceAcquiredBy: successPlan.ree.sourceAcquiredBy,
      sourceSnapshotArchive: successPlan.ree.sourceSnapshotArchive,
      sourceSnapshotCapturedAt: successPlan.ree.sourceSnapshotCapturedAt,
    },
    successMessage: successPlan.successMessage,
  };
}

export function planClearedSourceStateResult(): ClearedSourceStatePlan {
  return {
    reePatch: {
      origin_url: "",
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
