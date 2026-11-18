const API_V1_BASE = "/api/v1";

export const endpoints = {
  stores: () => `${API_V1_BASE}/stores`,
  workbenches: () => `${API_V1_BASE}/workbenches`,
  reeIndex: () => `${API_V1_BASE}/ree-index`,
  rees: () => `${API_V1_BASE}/rees`,
  buildInfo: () => `${API_V1_BASE}/system/build-info`,
  ree: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}`,
  reeState: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/state`,
  patchReeDefinition: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/patch-ree-definition`,
  acquireSource: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/acquire-source`,
  reeSourceUploadInit: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:upload-init`,
  reeSourceUploadComplete: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source:upload-complete`,
  reeBundleUploadInit: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree:upload-init`,
  loadReeBundle: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/load-ree-bundle`,
  removeSource: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/remove-source`,
  writeScript: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/write-script`,
  reeFileRaw: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/raw`,
  suggestScripts: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/suggest-scripts`,
  lintScripts: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/lint-scripts`,
  reeScriptTemplates: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/script-templates`,
  reeScriptLintDraft: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/script-lints:draft`,
  sealRee: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/seal-ree`,
  operationHistory: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/history`,
  reeArchive: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/ree-archive`,
  buildExperimentEnvironment: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/build-experiment-environment`,
  observeHardware: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/observe-hardware`,
  generateSbom: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/generate-sbom`,
  crossCheckSbom: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/cross-check-sbom`,
  activateExperimentEnvironment: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/activate-experiment-environment`,
  evaluateReproducibility: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/evaluate-reproducibility`,
  runExperiment: (reeId: string, experimentName: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/run-experiment/${encodeURIComponent(experimentName)}`,
  reproducibilityReport: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reproducibility-report`,
  reeReviews: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews`,
  reviewAcquireSource: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews/acquire-source`,
  reviewBuildExperimentEnvironment: (reeId: string, reviewId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews/${encodeURIComponent(reviewId)}/build-experiment-environment`,
  reviewActivateExperimentEnvironment: (reeId: string, reviewId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews/${encodeURIComponent(reviewId)}/activate-experiment-environment`,
  reviewRunExperiment: (reeId: string, reviewId: string, experimentName: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/reviews/${encodeURIComponent(reviewId)}/run-experiment/${encodeURIComponent(experimentName)}`,
  reeRuns: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs`,
  reeRun: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}`,
  reeRunCancel: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}:cancel`,
  reeRunLogs: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}/logs`,
};
