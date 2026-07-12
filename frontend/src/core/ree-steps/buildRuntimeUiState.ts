const SKIPPED_SENTINEL = "__skipped__";

export function resolvedRuntimePath(raw: string | null | undefined): string {
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

type RuntimeArtifactStatus = "unset" | "missing" | "ready";

export function runtimeArtifactStatus(input: {
  hasRuntime: boolean;
  runtimePathExists: boolean;
}): RuntimeArtifactStatus {
  if (!input.hasRuntime) return "unset";
  if (!input.runtimePathExists) return "missing";
  return "ready";
}

export function runtimeArtifactStatusLabel(status: RuntimeArtifactStatus): string {
  switch (status) {
    case "unset":
      return "Not set";
    case "missing":
      return "Missing";
    case "ready":
      return "Ready";
  }
}

export function runtimeSummaryStatusLabel(status: RuntimeArtifactStatus): string {
  switch (status) {
    case "unset":
      return "—";
    case "missing":
      return "Missing in workspace";
    case "ready":
      return "In workspace";
  }
}

export function buildFooterHint(input: {
  runDone: boolean;
  runFailed: boolean;
  hasScript: boolean;
}): string {
  if (input.runFailed) return "Build failed — check the log, then re-run.";
  if (input.runDone) return "Build complete — continue to SBOM.";
  return "Script ready. Run build when prerequisites are met.";
}

export function buildSummaryStatusLabel(input: { runDone: boolean; hasScript: boolean }): string {
  if (input.runDone) return "Built";
  return "Ready";
}

interface BuildReadiness {
  hasScript: boolean;
  runtimeReady: boolean;
  runDone: boolean;
  done: number;
  total: number;
  percent: number;
}

export function buildReadiness(input: {
  hasScript: boolean;
  hasRuntime: boolean;
  runtimePathExists: boolean;
  runDone: boolean;
}): BuildReadiness {
  const runtimeReady = input.hasRuntime && input.runtimePathExists;
  const checks = [input.hasScript, runtimeReady, input.runDone];
  const done = checks.filter(Boolean).length;
  return {
    hasScript: input.hasScript,
    runtimeReady,
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

export function deriveRuntimeFileSize(
  runtimeFile: { size?: number; content?: string } | null,
): string | null {
  if (!runtimeFile) return null;
  if (typeof runtimeFile.size === "number" && runtimeFile.size > 0) {
    return formatByteSize(runtimeFile.size);
  }
  const sizeMatch = (runtimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
  if (sizeMatch) {
    return sizeMatch[1];
  }
  const bytes = new TextEncoder().encode(runtimeFile.content || "").length;
  return formatByteSize(bytes);
}
