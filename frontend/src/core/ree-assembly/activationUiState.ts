export function activationRunLabel(input: { running: boolean; runDone: boolean }): string {
  if (input.running) return "Testing...";
  if (input.runDone) return "Re-run activation";
  return "Run activation";
}

export function canRunActivation(input: {
  running: boolean;
  hasMissing: boolean;
  runtimePathExists: boolean;
}): boolean {
  return !input.running && !input.hasMissing && input.runtimePathExists;
}

export function activationFooterHint(input: { runDone: boolean; runFailed: boolean }): string {
  if (input.runFailed) return "Activation failed — check the log, then re-run.";
  if (input.runDone) return "Activation passed for the current runtime artifact.";
  return "Run the smoke test after the runtime artifact and activation script are ready.";
}

interface ActivationReadiness {
  hasRuntime: boolean;
  runtimePathExists: boolean;
  runDone: boolean;
  done: number;
  total: number;
  percent: number;
}

export function activationReadiness(input: {
  hasRuntime: boolean;
  runtimePathExists: boolean;
  runDone: boolean;
}): ActivationReadiness {
  const checks = [input.hasRuntime, input.runtimePathExists, input.runDone];
  const done = checks.filter(Boolean).length;
  return {
    ...input,
    done,
    total: checks.length,
    percent: Math.round((done / checks.length) * 100),
  };
}
