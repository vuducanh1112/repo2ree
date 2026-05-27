export interface ExperimentOutputResult {
  sourceKey: string;
  mode: string;
  passed: boolean;
  detail: string;
}

export interface ExperimentRunOutputs {
  experimentName: string;
  mode: "verify" | "snapshot";
  exitCode: number | null;
  verdict?: "pass" | "fail";
  outputResults?: ExperimentOutputResult[];
  snapshotApplied?: boolean;
  snapshotCount?: number;
  snapshotMessage?: string;
  runtimePath?: string;
  runtimeImage?: string;
}
