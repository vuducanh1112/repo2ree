export type BuildScriptSourceKind = "picked" | "manual" | "generated";

export interface BuildScriptSource {
  kind: BuildScriptSourceKind;
  base?: string;
  edited?: boolean;
}

export type BuildScriptMode = "pick" | "write" | "generate";

export function modeForSource(source: BuildScriptSource | null): BuildScriptMode {
  if (source?.kind === "generated") return "generate";
  if (source?.kind === "manual") return "write";
  return "pick";
}

export function provenanceLabel(source: BuildScriptSource | null): string {
  if (!source) return "No script yet";
  if (source.kind === "picked") return "Picked from workspace";
  if (source.kind === "manual") return "Hand-written";
  const baseLabel = source.base ? ` · ${source.base}` : "";
  return `Generated${baseLabel}${source.edited ? " · edited" : ""}`;
}

export function sourceAfterGenerate(base: string): BuildScriptSource {
  return { kind: "generated", base, edited: false };
}

export function sourceAfterSave(previous: BuildScriptSource | null): BuildScriptSource {
  if (previous?.kind === "generated") return { ...previous, edited: true };
  return { kind: "manual" };
}

type BuildRunStatusLabel = "Building" | "Built" | "Ready" | "Empty";

export function buildRunStatusLabel(input: {
  running: boolean;
  runDone: boolean;
  hasScript: boolean;
}): BuildRunStatusLabel {
  if (input.running) return "Building";
  if (input.runDone) return "Built";
  if (input.hasScript) return "Ready";
  return "Empty";
}

type RuntimeArtifactStatus = "unset" | "missing" | "included" | "excluded";

export function runtimeArtifactStatus(input: {
  hasRuntime: boolean;
  runtimePathExists: boolean;
  includeRuntime: boolean;
}): RuntimeArtifactStatus {
  if (!input.hasRuntime) return "unset";
  if (!input.runtimePathExists) return "missing";
  return input.includeRuntime ? "included" : "excluded";
}

export function runtimeArtifactStatusLabel(status: RuntimeArtifactStatus): string {
  switch (status) {
    case "unset":
      return "Not set";
    case "missing":
      return "Missing";
    case "included":
      return "Included";
    case "excluded":
      return "Excluded";
  }
}

export function runtimeSummaryStatusLabel(status: RuntimeArtifactStatus): string {
  switch (status) {
    case "unset":
      return "—";
    case "missing":
      return "Missing in workspace";
    case "included":
      return "Bundled in REE";
    case "excluded":
      return "Selected · not bundled";
  }
}

export function buildFooterHint(input: { runDone: boolean; hasScript: boolean }): string {
  if (input.runDone) return "Build complete — continue to SBOM.";
  if (input.hasScript) return "Script ready. Run build when prerequisites are met.";
  return "Add a build script to begin.";
}

export function buildSummaryStatusLabel(input: { runDone: boolean; hasScript: boolean }): string {
  if (input.runDone) return "Built";
  if (input.hasScript) return "Ready";
  return "Empty";
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
