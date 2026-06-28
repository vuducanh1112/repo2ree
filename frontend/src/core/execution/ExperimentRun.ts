export interface ExperimentOutputResult {
  sourceKey: string;
  mode: string;
  passed: boolean;
  detail: string;
}

export interface ExperimentRunOutputs {
  // The runnable that was executed — an experiment's name, or "activation".
  subjectName: string;
  mode: "verify" | "snapshot";
  exitCode: number | null;
  verdict?: "pass" | "fail";
  outputResults?: ExperimentOutputResult[];
  snapshotApplied?: boolean;
  snapshotCount?: number;
  snapshotMessage?: string;
  runtimePath?: string;
}
