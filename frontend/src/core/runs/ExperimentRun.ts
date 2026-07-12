export interface ExperimentRunOutputs {
  // The runnable that was executed — an experiment's name, or "activation".
  subjectName: string;
  exitCode: number | null;
  // Exit code of the verify script; absent when no verify script is declared.
  verifyExitCode?: number | null;
  verdict?: "pass" | "fail";
  runtimePath?: string;
}
