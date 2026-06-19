export interface EvaluationState {
  dependencyLevel?: number;
  environmentLevel?: number;
  machineLevel?: number;
  // Machine-produced dependency summary, settled by the evaluate run alongside
  // the reproducibility levels (mirrors the backend session field).
  detectedDependencies?: string;
}

export function emptyEvaluationState(): EvaluationState {
  return { dependencyLevel: 0, environmentLevel: 0, machineLevel: 0, detectedDependencies: "" };
}
