export type ActivationScriptSourceKind = "picked" | "manual" | "generated";

export interface ActivationScriptSource {
  kind: ActivationScriptSourceKind;
  base?: string;
  edited?: boolean;
}

export type ActivationScriptMode = "pick" | "write" | "generate";

export function modeForActivationSource(
  source: ActivationScriptSource | null,
): ActivationScriptMode {
  if (source?.kind === "generated") return "generate";
  if (source?.kind === "manual") return "write";
  return "pick";
}

export function activationProvenanceLabel(source: ActivationScriptSource | null): string {
  if (!source) return "No script yet";
  if (source.kind === "picked") return "Picked from workspace";
  if (source.kind === "manual") return "Hand-written";
  const baseLabel = source.base ? ` · ${source.base}` : "";
  return `Generated${baseLabel}${source.edited ? " · edited" : ""}`;
}

export function activationSourceAfterGenerate(base: string): ActivationScriptSource {
  return { kind: "generated", base, edited: false };
}

export function activationSourceAfterSave(
  previous: ActivationScriptSource | null,
): ActivationScriptSource {
  if (previous?.kind === "generated") return { ...previous, edited: true };
  return { kind: "manual" };
}

export function activationRunLabel(input: { running: boolean; runDone: boolean }): string {
  if (input.running) return "Testing...";
  if (input.runDone) return "Re-run activation";
  return "Run activation";
}

export function canRunActivation(input: {
  running: boolean;
  hasMissing: boolean;
  runtimePathExists: boolean;
  scriptFileMissing: boolean;
}): boolean {
  return !input.running && !input.hasMissing && input.runtimePathExists && !input.scriptFileMissing;
}

export function activationFooterHint(input: { runDone: boolean }): string {
  if (input.runDone) return "Activation passed for the current runtime artifact.";
  return "Run the smoke test after the runtime artifact and activation script are ready.";
}

interface ActivationReadiness {
  hasRuntime: boolean;
  runtimePathExists: boolean;
  hasScript: boolean;
  scriptPresent: boolean;
  runDone: boolean;
  done: number;
  total: number;
  percent: number;
}

export function activationReadiness(input: {
  hasRuntime: boolean;
  runtimePathExists: boolean;
  hasScript: boolean;
  scriptPresent: boolean;
  runDone: boolean;
}): ActivationReadiness {
  const checks = [
    input.hasRuntime,
    input.runtimePathExists,
    input.hasScript && input.scriptPresent,
    input.runDone,
  ];
  const done = checks.filter(Boolean).length;
  return {
    ...input,
    done,
    total: checks.length,
    percent: Math.round((done / checks.length) * 100),
  };
}
