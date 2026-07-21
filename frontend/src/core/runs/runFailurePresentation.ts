import type { ReeRunFailure, ReeRunFailureCategory } from "./ReeRun";

/**
 * How a failure should read in the UI. ``tone`` splits failures into the three
 * classes the API user actually cares about — a transient outage worth
 * retrying, an actionable rejection (conflict / bad request), or a genuine
 * fault — so surfaces can style and word them differently instead of painting
 * every non-success the same red.
 */
export type ReeRunFailureTone = "transient" | "rejected" | "fault";

interface ReeRunFailurePresentation {
  /** Short, human-readable label for the failure class. */
  label: string;
  tone: ReeRunFailureTone;
  /** Whether the caller may safely re-issue the same operation. */
  retryable: boolean;
  /** The underlying failure message, for detail/tooltip display. */
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

/**
 * Reduce a typed {@link ReeRunFailure} to display-ready facts. Pure and
 * category-driven so the same policy applies wherever a failure surfaces — run
 * HUD, sync request errors — and can be unit-tested without React.
 *
 * ``retryable`` prefers the backend's explicit signal (a component may know its
 * specific failure is or is not safe to retry) and only falls back to the
 * category's default tone when the flag is absent.
 */
export function runFailurePresentation(failure: ReeRunFailure): ReeRunFailurePresentation {
  const tone = CATEGORY_TONES[failure.category] ?? "fault";
  return {
    label: CATEGORY_LABELS[failure.category] ?? "Run failed",
    tone,
    retryable: failure.retryable,
    message: failure.message,
  };
}
