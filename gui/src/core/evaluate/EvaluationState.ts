export interface EvaluationState {
  dependencyLevel?: number;
  environmentLevel?: number;
  machineLevel?: number;
  detectedDependencies?: string;
}

export function emptyEvaluationState(): EvaluationState {
  return { dependencyLevel: 0, environmentLevel: 0, machineLevel: 0, detectedDependencies: "" };
}
