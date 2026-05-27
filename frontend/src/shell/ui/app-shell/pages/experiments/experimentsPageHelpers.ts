export function expId(index: number) {
  return `EXP-${String(index + 1).padStart(3, "0")}`;
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
