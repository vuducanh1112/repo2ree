import type { ReeExperiment } from "./ReeSpec";

export function expId(index: number) {
  return `EXP-${String(index + 1).padStart(3, "0")}`;
}

interface ExperimentValidation {
  trimmedName: string;
  isDuplicateName: boolean;
  isInvalidName: boolean;
  canRun: boolean;
}

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

export function experimentIndexFromField(field: string | null): number | null {
  const match = field?.match(/^experiments\[(\d+)\]/);
  return match ? Number(match[1]) : null;
}

const EXPERIMENT_NAME_PATTERN = /^[A-Za-z0-9 ._-]+$/;

export function isValidExperimentName(name: string): boolean {
  if (name === "") return true;
  if (name === "." || name === "..") return false;
  return EXPERIMENT_NAME_PATTERN.test(name);
}
