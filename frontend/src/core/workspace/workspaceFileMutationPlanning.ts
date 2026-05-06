interface WorkspaceFilePersistencePlan {
  normalizedPreviousPath?: string;
  normalizedPath: string;
  shouldDeletePrevious: boolean;
  successMessage: string;
}

interface WorkspaceFileDownloadPlan {
  downloadName: string;
  successMessage: string;
}

interface ReeArchiveDownloadPlan {
  archiveFileName: string;
  successMessage: string;
}

function sanitizeDownloadName(name: string): string {
  return name.replace(/\\/g, "_");
}

export function planWorkspaceFilePersistence(
  previousPath: string | undefined,
  path: string,
): WorkspaceFilePersistencePlan {
  const normalizedPreviousPath = (previousPath || "").trim() || undefined;
  const normalizedPath = path.trim();

  return {
    normalizedPreviousPath,
    normalizedPath,
    shouldDeletePrevious: !!normalizedPreviousPath && normalizedPreviousPath !== normalizedPath,
    successMessage: `Saved ${normalizedPath} to workspace`,
  };
}

export function planWorkspaceFileDownload(
  path: string,
  suggestedName?: string,
): WorkspaceFileDownloadPlan {
  const fallbackName = path.split("/").pop() || "workspace-file";
  const downloadName = sanitizeDownloadName(suggestedName || fallbackName);

  return {
    downloadName,
    successMessage: `Downloaded ${downloadName}`,
  };
}

export function planReeArchiveDownload(
  reeName: string,
  archiveFileName?: string,
): ReeArchiveDownloadPlan {
  const fallbackReeName = reeName.trim().replace(/[^A-Za-z0-9._-]+/g, "_") || "ree";
  const resolvedArchiveFileName = archiveFileName || `${fallbackReeName}.zip`;

  return {
    archiveFileName: resolvedArchiveFileName,
    successMessage: `Downloaded ${resolvedArchiveFileName}`,
  };
}
