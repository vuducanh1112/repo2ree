import type { ReeExperiment } from "./ReeSpec";

export function expId(index: number) {
  return `EXP-${String(index + 1).padStart(3, "0")}`;
}

interface ExperimentValidation {
  trimmedName: string;
  isDuplicateName: boolean;
  isInvalidName: boolean;
  /** Runnable: uniquely named, valid name, and a command to execute. */
  canRun: boolean;
}

// Single source of truth for an experiment's runnability, shared by the detail
// body (field validation) and the page header (Run enablement).
export function experimentValidation(
  experiment: ReeExperiment,
  otherNames: string[],
): ExperimentValidation {
  const trimmedName = experiment.name.trim();
  const isDuplicateName = trimmedName !== "" && otherNames.includes(trimmedName);
  const isInvalidName = !isValidExperimentName(experiment.name);
  const canRun =
    trimmedName !== "" && !isDuplicateName && !isInvalidName && experiment.runScript.trim() !== "";
  return { trimmedName, isDuplicateName, isInvalidName, canRun };
}

// focusedField doubles as the deep-link into a specific experiment: a value like
// "experiments[2].name" means "open experiment #2's editor". Returns the index,
// or null when the field doesn't target an experiment.
export function experimentIndexFromField(field: string | null): number | null {
  const match = field?.match(/^experiments\[(\d+)\]/);
  return match ? Number(match[1]) : null;
}

// Mirrors the backend Experiment.name validator: names are used as a URL path
// segment when running an experiment, so they must avoid "/" (and the "." /
// ".." path segments). Keep this in sync with EXPERIMENT_NAME_PATTERN in
// core/src/repo2ree_core/experiment/experiment.py.
const EXPERIMENT_NAME_PATTERN = /^[A-Za-z0-9 ._-]+$/;

export function isValidExperimentName(name: string): boolean {
  if (name === "") return true; // in-progress drafts may not be named yet
  if (name === "." || name === "..") return false;
  return EXPERIMENT_NAME_PATTERN.test(name);
}
