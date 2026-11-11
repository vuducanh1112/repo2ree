export function activationRunLabel(input: { running: boolean; runDone: boolean }): string {
  if (input.running) return "Testing...";
  if (input.runDone) return "Re-run activation";
  return "Run activation";
}

export function canRunActivation(input: {
  running: boolean;
  hasMissing: boolean;
  experimentEnvironmentPathExists: boolean;
}): boolean {
  return !input.running && !input.hasMissing && input.experimentEnvironmentPathExists;
}

export function activationFooterHint(input: { runDone: boolean; runFailed: boolean }): string {
  if (input.runFailed) return "Activation failed — check the log, then re-run.";
  if (input.runDone) return "Activation passed for the current experiment environment artifact.";
  return "Run the activation once the experiment environment artifact and the activate script are ready.";
}

interface ActivationReadiness {
  hasExperimentEnvironment: boolean;
  experimentEnvironmentPathExists: boolean;
  runDone: boolean;
  done: number;
  total: number;
  percent: number;
}

export function activationReadiness(input: {
  hasExperimentEnvironment: boolean;
  experimentEnvironmentPathExists: boolean;
  runDone: boolean;
}): ActivationReadiness {
  const checks = [
    input.hasExperimentEnvironment,
    input.experimentEnvironmentPathExists,
    input.runDone,
  ];
  const done = checks.filter(Boolean).length;
  return {
    ...input,
    done,
    total: checks.length,
    percent: Math.round((done / checks.length) * 100),
  };
}
