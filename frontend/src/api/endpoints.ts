const API_V1_BASE = "/api/v1";

export const endpoints = {
  workspaces: () => `${API_V1_BASE}/rees`,
  workspace: (workspaceId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}`,
  workspaceSourceAcquire: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/source:acquire`,
  workspaceSourceUploadInit: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/source:upload-init`,
  workspaceSourceUploadComplete: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/source:upload-complete`,
  workspaceSource: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/source`,
  workspaceFiles: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/files`,
  workspaceFileContent: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/files/content`,
  workspaceFileRaw: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/files/raw`,
  workspaceReeArchive: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/ree-archive`,
  workspaceBuildRuntime: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/build-runtime`,
  workspaceGenerateHbom: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/generate-hbom`,
  workspaceGenerateSbom: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/generate-sbom`,
  workspaceActivationTest: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/activation-test`,
  workspaceEvaluate: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/evaluate`,
  workspaceRuns: (workspaceId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/runs`,
  workspaceRun: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}`,
  workspaceRunCancel: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}:cancel`,
  workspaceRunRetry: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}:retry`,
  workspaceRunLogs: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}/logs`,
  reviewUploadInit: () => `${API_V1_BASE}/reviews:upload-init`,
  reviewUploadBytes: (reviewId: string, uploadToken: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/upload/${encodeURIComponent(uploadToken)}`,
  reviewUploadComplete: (reviewId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}:upload-complete`,
  review: (reviewId: string) => `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}`,
  reviewSourceAcquire: (reviewId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/source:acquire`,
  reviewBuildRuntime: (reviewId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/build-runtime`,
  reviewActivationTest: (reviewId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/activation-test`,
  reviewRun: (reviewId: string, runId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/runs/${encodeURIComponent(runId)}`,
  reviewRunCancel: (reviewId: string, runId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/runs/${encodeURIComponent(runId)}:cancel`,
  reviewRunLogs: (reviewId: string, runId: string) =>
    `${API_V1_BASE}/reviews/${encodeURIComponent(reviewId)}/runs/${encodeURIComponent(runId)}/logs`,
};
