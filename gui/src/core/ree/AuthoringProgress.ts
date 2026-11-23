import { isOneOf, requireKnownNames } from "@core/contract/unknownNames";
import { STEP_KEYS, type StepKey } from "@core/generated/vocabulary";

export const AUTHORING_STEP_KEYS = STEP_KEYS.filter(
  (key): key is Exclude<StepKey, "check_working_environment"> =>
    key !== "check_working_environment",
);

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
  next: AuthoringStepKey | undefined;
}

export const NO_AUTHORING_PROGRESS: AuthoringProgress = { steps: [], next: undefined };

const STATUSES: readonly AuthoringStepStatus[] = ["complete", "ready", "blocked"];

function isStepKey(value: unknown): value is AuthoringStepKey {
  return isOneOf(AUTHORING_STEP_KEYS, value);
}

export function mapRawAuthoringProgress(raw: unknown): AuthoringProgress {
  const progress = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const steps = (Array.isArray(progress.steps) ? progress.steps : []).map((value) =>
    value && typeof value === "object" ? (value as Record<string, unknown>) : {},
  );
  requireKnownNames("steps", STEP_KEYS, [
    ...steps.flatMap((step) => [step.key, ...(Array.isArray(step.requires) ? step.requires : [])]),
    ...(progress.next == null ? [] : [progress.next]),
  ]);
  const known = steps.flatMap((step): AuthoringStep[] => {
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
