// Pure classifier over the backend's per-step consistency report (recorded
// run receipts vs. the current workspace tree, computed by
// repo2ree_core.receipts and carried on the workspace payload). The frontend
// never re-derives digests — it only maps the report to seal-gate warnings
// and step-badge staleness. Saving a script flips the derived state
// automatically: the refetched payload carries a new current digest.

export type ConsistencyStepStatus = "fresh" | "stale" | "missing";

export interface ConsistencyStaleInput {
  input: string;
  recorded: string | null;
  current: string | null;
}

export interface ConsistencyStep {
  step: string;
  status: ConsistencyStepStatus;
  runId?: string;
  recordedAt?: string;
  staleInputs?: ConsistencyStaleInput[];
  workspaceDrift?: "clean" | "modified" | "unknown";
}

export interface ConsistencyReport {
  steps: ConsistencyStep[];
}

/** A stale step rendered in the seal confirm gate, beside the missing panels. */
export interface StaleSealItem {
  key: string;
  label: string;
  detail: string;
}

const EXPERIMENT_STEP_PREFIX = "experiment:";

const STEP_LABELS: Record<string, string> = {
  build_runtime: "Build",
  generate_sbom: "SBOM",
  activation_test: "Activation",
};

const INPUT_PHRASES: Record<string, string> = {
  snapshot: "source snapshot changed",
  buildScript: "build script changed",
  activationScript: "activation script changed",
  experimentScript: "run script changed",
  runtimeArtifact: "runtime artifact changed",
  verifyScript: "verify script changed",
  producedOutput: "output changed since the recorded run",
};

function stepLabel(step: string): string {
  if (step.startsWith(EXPERIMENT_STEP_PREFIX)) {
    return `Experiment “${step.slice(EXPERIMENT_STEP_PREFIX.length)}”`;
  }
  return STEP_LABELS[step] ?? step;
}

function staleDetail(step: ConsistencyStep): string {
  const phrases = (step.staleInputs ?? []).map(
    (entry) => INPUT_PHRASES[entry.input] ?? `${entry.input} changed`,
  );
  return phrases.join(", ") || "inputs changed since the recorded run";
}

/**
 * The stale steps to warn about in the seal gate: results whose recorded
 * inputs no longer match the tree being sealed. Missing steps are not listed
 * here — absence is the existing missing-panel gate's concern.
 */
export function staleSealItems(report: ConsistencyReport | undefined): StaleSealItem[] {
  return (report?.steps ?? [])
    .filter((step) => step.status === "stale")
    .map((step) => ({
      key: step.step,
      label: stepLabel(step.step),
      detail: staleDetail(step),
    }));
}

// Consistency steps → step keys (which double as canvas node
// page keys; see PAGE in the shell). Every stale experiment ambers the one
// Experiments node.
const CONSISTENCY_STEP_TO_STEP_KEY: Record<string, string> = {
  build_runtime: "build",
  generate_sbom: "sbom",
  activation_test: "activation",
};

/** Step keys whose recorded result is stale, for badge amber-ing. */
export function staleStepKeys(report: ConsistencyReport | undefined): ReadonlySet<string> {
  const keys = new Set<string>();
  for (const step of report?.steps ?? []) {
    if (step.status !== "stale") continue;
    if (step.step.startsWith(EXPERIMENT_STEP_PREFIX)) {
      keys.add("experiments");
    } else {
      const key = CONSISTENCY_STEP_TO_STEP_KEY[step.step];
      if (key) keys.add(key);
    }
  }
  return keys;
}
