const API_V1_BASE = "/api/v1";

export const endpoints = {
  workbenchImages: () => `${API_V1_BASE}/workbench/images`,
  scriptTemplates: () => `${API_V1_BASE}/script-templates`,
  agents: () => `${API_V1_BASE}/agents`,
  rees: () => `${API_V1_BASE}/rees`,
  ree: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}`,
  reeIntent: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/intent`,
  reeSourceAcquire: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:acquire`,
  reeSourceUploadInit: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:upload-init`,
  reeSourceUploadComplete: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:upload-complete`,
  reeBundleUploadInit: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree:upload-init`,
  reeBundleLoad: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree:load`,
  reeSource: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source`,
  reeFileContent: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/content`,
  reeFileRaw: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/raw`,
  reeScriptInferences: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/script-inferences:generate`,
  reeSeal: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree:seal`,
  reeArchive: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree-archive`,
  reeWorkbenchReprovision: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/workbench/reprovision`,
  reeBuildRuntime: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/build-runtime`,
  reeGenerateHbom: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/generate-hbom`,
  reeGenerateSbom: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/generate-sbom`,
  reeCrossCheckSbom: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/cross-check-sbom`,
  reeActivationTest: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/activation-test`,
  reeEvaluate: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/evaluate`,
  reeExperimentRun: (reeId: string, experimentName: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/experiments/${encodeURIComponent(experimentName)}:run`,
  reeEvaluateReport: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/evaluate/report`,
  reeScorecard: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/scorecard`,
  reeAuthorReceipts: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/receipts/author`,
  reeReviews: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews`,
  reeSourceReview: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews/source:reproduce`,
  reeBuildReview: (reeId: string, reviewId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews/${encodeURIComponent(reviewId)}/build:reproduce`,
  reeRuns: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs`,
  reeRun: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}`,
  reeRunCancel: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}:cancel`,
  reeRunLogs: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}/logs`,
};
