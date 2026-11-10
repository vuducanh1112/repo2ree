const SKIPPED_SENTINEL = "__skipped__";

export function resolvedExperimentEnvironmentPath(raw: string | null | undefined): string {
  return raw && raw !== SKIPPED_SENTINEL ? raw : "";
}

type BuildRunStatusLabel = "Building" | "Built" | "Build failed" | "Ready";

export function buildRunStatusLabel(input: {
  running: boolean;
  runDone: boolean;
  runFailed: boolean;
  hasScript: boolean;
}): BuildRunStatusLabel {
  if (input.running) return "Building";
  if (input.runFailed) return "Build failed";
  if (input.runDone) return "Built";
  return "Ready";
}

// The runtime path is a declaration made before the build, not a pick made
// after it: the author says where the build script will write the artifact, and
// the build refuses to run without it and fails if nothing lands there. So an
// undeclared path is the author's missing input, while a declared path with no
// file yet is simply a build that has not run.
type ExperimentEnvironmentArtifactStatus = "undeclared" | "declared" | "produced";

export function experimentEnvironmentArtifactStatus(input: {
  hasExperimentEnvironment: boolean;
  experimentEnvironmentPathExists: boolean;
}): ExperimentEnvironmentArtifactStatus {
  if (!input.hasExperimentEnvironment) return "undeclared";
  if (!input.experimentEnvironmentPathExists) return "declared";
  return "produced";
}

export function experimentEnvironmentArtifactStatusLabel(
  status: ExperimentEnvironmentArtifactStatus,
): string {
  switch (status) {
    case "undeclared":
      return "Not declared";
    case "declared":
      return "Awaiting build";
    case "produced":
      return "Built";
  }
}

export function experimentEnvironmentSummaryStatusLabel(
  status: ExperimentEnvironmentArtifactStatus,
): string {
  switch (status) {
    case "undeclared":
      return "—";
    case "declared":
      return "Declared, not built";
    case "produced":
      return "In workspace";
  }
}

export function canRunBuild(input: {
  running: boolean;
  hasMissing: boolean;
  hasScript: boolean;
  hasExperimentEnvironmentPath: boolean;
}): boolean {
  return (
    !input.running && !input.hasMissing && input.hasScript && input.hasExperimentEnvironmentPath
  );
}

export function buildFooterHint(input: {
  runDone: boolean;
  runFailed: boolean;
  hasScript: boolean;
  hasExperimentEnvironmentPath: boolean;
}): string {
  if (input.runFailed) return "Build failed — check the log, then re-run.";
  if (input.runDone) return "Build complete — continue to SBOM.";
  if (!input.hasExperimentEnvironmentPath) {
    return "Declare where the build writes the experiment environment, then run build.";
  }
  return "Script ready. Run build when prerequisites are met.";
}

export function buildSummaryStatusLabel(input: { runDone: boolean; hasScript: boolean }): string {
  if (input.runDone) return "Built";
  return "Ready";
}

interface BuildReadiness {
  hasScript: boolean;
  experimentEnvironmentReady: boolean;
  runDone: boolean;
  done: number;
  total: number;
  percent: number;
}

export function buildReadiness(input: {
  hasScript: boolean;
  hasExperimentEnvironment: boolean;
  experimentEnvironmentPathExists: boolean;
  runDone: boolean;
}): BuildReadiness {
  const experimentEnvironmentReady =
    input.hasExperimentEnvironment && input.experimentEnvironmentPathExists;
  const checks = [input.hasScript, experimentEnvironmentReady, input.runDone];
  const done = checks.filter(Boolean).length;
  return {
    hasScript: input.hasScript,
    experimentEnvironmentReady,
    runDone: input.runDone,
    done,
    total: checks.length,
    percent: Math.round((done / checks.length) * 100),
  };
}

function formatByteSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function deriveExperimentEnvironmentFileSize(
  experimentEnvironmentFile: { size?: number; content?: string } | null,
): string | null {
  if (!experimentEnvironmentFile) return null;
  if (typeof experimentEnvironmentFile.size === "number" && experimentEnvironmentFile.size > 0) {
    return formatByteSize(experimentEnvironmentFile.size);
  }
  const sizeMatch = (experimentEnvironmentFile.content || "").match(
    /Size:\s*(~?[\d.]+ ?[KMGT]?B)/i,
  );
  if (sizeMatch) {
    return sizeMatch[1];
  }
  const bytes = new TextEncoder().encode(experimentEnvironmentFile.content || "").length;
  return formatByteSize(bytes);
}
