const API_V1_BASE = "/api/v1";

export const endpoints = {
  rees: () => `${API_V1_BASE}/rees`,
  ree: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}`,
  reeDraft: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/draft`,
  reeSourceAcquire: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:acquire`,
  reeSourceUploadInit: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:upload-init`,
  reeSourceUploadComplete: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:upload-complete`,
  reeSource: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source`,
  reeFileContent: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/content`,
  reeFileRaw: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/raw`,
  reeArchive: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree-archive`,
  reeBuildRuntime: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/build-runtime`,
  reeGenerateHbom: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/generate-hbom`,
  reeGenerateSbom: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/generate-sbom`,
  reeActivationTest: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/activation-test`,
  reeEvaluate: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/evaluate`,
  reeRun: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}`,
  reeRunCancel: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}:cancel`,
  reeRunLogs: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}/logs`,
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
