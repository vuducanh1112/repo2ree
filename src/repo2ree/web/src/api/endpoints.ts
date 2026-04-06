const API_V1_BASE = "/api/v1";

export const endpoints = {
  workspaces: () => `${API_V1_BASE}/workspaces`,
  workspace: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}`,
  workspaceSourceAcquire: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/source:acquire`,
  workspaceSourceUploadInit: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/source:upload-init`,
  workspaceSourceUploadComplete: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/source:upload-complete`,
  workspaceSource: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/source`,
  workspaceFiles: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/files`,
  workspaceFileContent: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/files/content`,
  workspaceFileRaw: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/files/raw`,
  workspaceReeArchive: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/ree-archive`,
  workspaceBuildRuntime: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/build-runtime`,
  workspaceGenerateSbom: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/generate-sbom`,
  workspaceActivationTest: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/activation-test`,
  workspaceRuns: (workspaceId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/runs`,
  workspaceRun: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}`,
  workspaceRunCancel: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}:cancel`,
  workspaceRunRetry: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}:retry`,
  workspaceRunLogs: (workspaceId: string, runId: string) =>
    `${API_V1_BASE}/workspaces/${encodeURIComponent(workspaceId)}/runs/${encodeURIComponent(runId)}/logs`,
};
