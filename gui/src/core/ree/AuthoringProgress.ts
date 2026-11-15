// Where the REE stands on each authoring step, as its own records say. The REE
// document carries it (`steps`); the shell reads it rather than deriving it, so
// the GUI says what `ree steps` says.

export const AUTHORING_STEP_KEYS = [
  "source",
  "metadata",
  "hbom",
  "evaluate",
  "build_experiment_environment",
  "sbom",
  "crosscheck",
  "activation",
  "experiments",
  "seal",
] as const;

export type AuthoringStepKey = (typeof AUTHORING_STEP_KEYS)[number];

export type AuthoringStepStatus = "complete" | "ready" | "blocked";

export interface AuthoringStep {
  key: AuthoringStepKey;
  order: number;
  label: string;
  requires: readonly AuthoringStepKey[];
  status: AuthoringStepStatus;
}

export interface AuthoringProgress {
  steps: readonly AuthoringStep[];
  /** The step to do next: the first ready one. */
  next: AuthoringStepKey | undefined;
}

export const NO_AUTHORING_PROGRESS: AuthoringProgress = { steps: [], next: undefined };

const STATUSES: readonly AuthoringStepStatus[] = ["complete", "ready", "blocked"];

function isStepKey(value: unknown): value is AuthoringStepKey {
  return AUTHORING_STEP_KEYS.includes(value as AuthoringStepKey);
}

export function mapRawAuthoringProgress(raw: unknown): AuthoringProgress {
  const progress = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const steps = Array.isArray(progress.steps) ? progress.steps : [];
  const known = steps.flatMap((value): AuthoringStep[] => {
    const step = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
    if (!isStepKey(step.key)) return [];
    return [
      {
        key: step.key,
        order: Number(step.order ?? 0),
        label: String(step.label ?? step.key),
        requires: Array.isArray(step.requires) ? step.requires.filter(isStepKey) : [],
        status: STATUSES.includes(step.status as AuthoringStepStatus)
          ? (step.status as AuthoringStepStatus)
          : "blocked",
      },
    ];
  });
  // A step this GUI has no page for (the working environment check) is not offered as the next one: the first
  // ready step it can show is.
  const fallback = known
    .filter((step) => step.status === "ready")
    .sort((a, b) => a.order - b.order)[0]?.key;
  return { steps: known, next: isStepKey(progress.next) ? progress.next : fallback };
}

export function isAuthoringStepComplete(
  progress: AuthoringProgress,
  key: AuthoringStepKey,
): boolean {
  return progress.steps.some((step) => step.key === key && step.status === "complete");
}
