import type { FileTreeNode, Ree } from "../../types";
import { normalizeSnapshotArchiveName } from "../../utils";

interface SourcePlanSuccess<T> {
  ok: true;
  value: T;
}

interface SourcePlanFailure {
  ok: false;
  error: string;
}

type SourcePlanResult<T> = SourcePlanSuccess<T> | SourcePlanFailure;

interface DownloadSourcePlan {
  normalizedSourceUrl: string;
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

function snapshotArchiveNameFromSourceUrl(sourceUrl: string): string {
  const repoBase =
    (sourceUrl.split("/").filter(Boolean).pop() || "source").replace(
      /\.(git|tar\.gz|tgz|zip)$/i,
      "",
    ) || "source";

  return normalizeSnapshotArchiveName(`${repoBase}-original.tar.gz`);
}

export function planSourceDownload(
  ree: Ree,
  originType: Ree["source_type"],
  sourceUrl: string,
): SourcePlanResult<DownloadSourcePlan> {
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
    value: {
      normalizedSourceUrl,
    },
  };
}

export function planSourceUpload(ree: Ree): SourcePlanResult<Record<string, never>> {
  if (ree._sourceAvailable && ree._sourceAcquiredBy === "download") {
    return {
      ok: false,
      error: "Source already provided via origin download. Change source to switch method.",
    };
  }

  return { ok: true, value: {} };
}

export function planDownloadedSourceSuccess(args: {
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

export function planUploadedSourceSuccess(args: {
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

export function planClearedSourceState(ree: Ree): Ree {
  return {
    ...ree,
    origin_url: "",
    _sourceAvailable: false,
    _sourceAcquiredBy: undefined,
    _uploadedArchive: "",
    _sourceSnapshotArchive: "",
    _sourceSnapshotCapturedAt: "",
  };
}
