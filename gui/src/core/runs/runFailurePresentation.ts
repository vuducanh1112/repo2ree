import type { ReeRunFailure, ReeRunFailureCategory } from "./ReeRun";

export type ReeRunFailureTone = "transient" | "rejected" | "fault";

interface ReeRunFailurePresentation {
  label: string;
  tone: ReeRunFailureTone;
  retryable: boolean;
  message: string;
}

const CATEGORY_LABELS: Record<ReeRunFailureCategory, string> = {
  validation: "Invalid request",
  precondition: "Precondition not met",
  conflict: "Conflict",
  execution: "Run failed",
  timeout: "Timed out",
  unavailable: "Workbench unavailable",
  internal: "Internal error",
};

const CATEGORY_TONES: Record<ReeRunFailureCategory, ReeRunFailureTone> = {
  validation: "rejected",
  precondition: "rejected",
  conflict: "rejected",
  execution: "fault",
  timeout: "transient",
  unavailable: "transient",
  internal: "fault",
};

export function runFailurePresentation(failure: ReeRunFailure): ReeRunFailurePresentation {
  const tone = CATEGORY_TONES[failure.category] ?? "fault";
  return {
    label: CATEGORY_LABELS[failure.category] ?? "Run failed",
    tone,
    retryable: failure.retryable,
    message: failure.message,
  };
}
