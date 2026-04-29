import type { FileTreeNode, Ree } from "../../types";
import { normalizeSnapshotArchiveName } from "../../utils";

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
  ree: Ree;
  successMessage: string;
}

interface UploadSourceSuccessPlan extends SourceSnapshotPlan {
  ree: Ree;
  successMessage: string;
}

interface SourceStatePlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  snapshotFiles: FileTreeNode[];
  snapshotArchiveName: string;
  reePatch: Partial<Ree>;
  successMessage: string;
}

interface ClearedSourceStatePlan {
  reePatch: Partial<Ree>;
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
  ree: Ree,
  originType: Ree["source_type"],
  sourceUrl: string,
): SourceActionPlanResult<{ normalizedSourceUrl: string }> {
  if (ree._sourceAvailable && ree._sourceAcquiredBy === "upload") {
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

function validateSourceUpload(ree: Ree): SourceActionPlanResult<Record<string, never>> {
  if (ree._sourceAvailable && ree._sourceAcquiredBy === "download") {
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
  ree: Ree;
  originType: Ree["source_type"];
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
      _sourceAvailable: sourceAvailable,
      _sourceAcquiredBy: "download",
      _uploadedArchive: "",
      _sourceSnapshotArchive: snapshotArchiveName,
      _sourceSnapshotCapturedAt: args.timestamp,
    },
    successMessage:
      args.originType === "tarball"
        ? "Tarball downloaded and extracted into workspace"
        : "Source files downloaded into workspace",
  };
}

function buildUploadedSourceSuccess(args: {
  ree: Ree;
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
      _sourceIncluded: true,
      _uploadedArchive: args.archiveName,
      source_type: "",
      _sourceAvailable: sourceAvailable,
      _sourceAcquiredBy: "upload",
      _sourceSnapshotArchive: snapshotArchiveName,
      _sourceSnapshotCapturedAt: args.timestamp,
    },
    successMessage: "Archive extracted into workspace",
  };
}

export function planSourceDownloadAction(
  ree: Ree,
  originType: Ree["source_type"],
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
  ree: Ree,
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
  ree: Ree;
  originType: Ree["source_type"];
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
      _sourceAvailable: successPlan.ree._sourceAvailable,
      _sourceAcquiredBy: successPlan.ree._sourceAcquiredBy,
      _uploadedArchive: successPlan.ree._uploadedArchive,
      _sourceSnapshotArchive: successPlan.ree._sourceSnapshotArchive,
      _sourceSnapshotCapturedAt: successPlan.ree._sourceSnapshotCapturedAt,
    },
    successMessage: successPlan.successMessage,
  };
}

export function planUploadedSourceState(args: {
  ree: Ree;
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
      _sourceIncluded: successPlan.ree._sourceIncluded,
      _uploadedArchive: successPlan.ree._uploadedArchive,
      source_type: successPlan.ree.source_type,
      _sourceAvailable: successPlan.ree._sourceAvailable,
      _sourceAcquiredBy: successPlan.ree._sourceAcquiredBy,
      _sourceSnapshotArchive: successPlan.ree._sourceSnapshotArchive,
      _sourceSnapshotCapturedAt: successPlan.ree._sourceSnapshotCapturedAt,
    },
    successMessage: successPlan.successMessage,
  };
}

export function planClearedSourceStateResult(): ClearedSourceStatePlan {
  return {
    reePatch: {
      origin_url: "",
      _sourceAvailable: false,
      _sourceAcquiredBy: undefined,
      _uploadedArchive: "",
      _sourceSnapshotArchive: "",
      _sourceSnapshotCapturedAt: "",
    },
    snapshotFiles: [],
    snapshotArchiveName: "",
    infoMessage: "Source files removed from workspace — choose download or upload again",
  };
}
