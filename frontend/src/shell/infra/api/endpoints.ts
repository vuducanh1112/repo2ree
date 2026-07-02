const API_V1_BASE = "/api/v1";

export const endpoints = {
  workbenchImages: () => `${API_V1_BASE}/workbench/images`,
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
  reeSource: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/source`,
  reeFileContent: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/content`,
  reeFileRaw: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/files/raw`,
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
  reeActivationTest: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/activation-test`,
  reeEvaluate: (reeId: string) => `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/evaluate`,
  reeExperimentRun: (reeId: string, experimentName: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/experiments/${encodeURIComponent(experimentName)}:run`,
  reeEvaluateReport: (reeId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/evaluate/report`,
  reeRun: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}`,
  reeRunCancel: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}:cancel`,
  reeRunLogs: (reeId: string, runId: string) =>
    `${API_V1_BASE}/rees/${encodeURIComponent(reeId)}/runs/${encodeURIComponent(runId)}/logs`,
};
