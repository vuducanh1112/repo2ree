export interface ExperimentRunOutputs {
  subjectName: string;
  exitCode: number | null;
  verifyExitCode?: number | null;
  verdict?: "pass" | "fail";
  experimentEnvironmentPath?: string;
}
