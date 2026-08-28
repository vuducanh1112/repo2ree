import type { LintFinding, LintReport, LintTierStatus } from "@shell/infra/api/apiTypes";

export type LintTargetKind =
  | "build"
  | "activation_run"
  | "activation_verify"
  | "experiment_run"
  | "experiment_verify";

export interface LintTarget {
  kind: LintTargetKind;
  experimentName?: string;
}

type FindingTone = "error" | "warn" | "info";

export function findingTone(severity: LintFinding["severity"]): FindingTone {
  if (severity === "error") return "error";
  if (severity === "warning") return "warn";
  return "info";
}

interface FindingSummary {
  headline: string;
  blocking: number;
}

type AnalysisState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "clean"; unrun: LintTierStatus[] }
  | {
      kind: "findings";
      findings: LintFinding[];
      summary: FindingSummary;
      unrun: LintTierStatus[];
    }
  | { kind: "error"; message: string };

export function unrunTiers(tiers: LintTierStatus[]): LintTierStatus[] {
  return tiers.filter((tier) => tier.status !== "ran");
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function summarize(findings: LintFinding[]): FindingSummary {
  const counts = { error: 0, warning: 0, info: 0 };
  for (const finding of findings) counts[finding.severity] += 1;

  const parts: string[] = [];
  if (counts.error > 0) parts.push(plural(counts.error, "error"));
  if (counts.warning > 0) parts.push(plural(counts.warning, "warning"));
  if (counts.info > 0) parts.push(plural(counts.info, "note"));

  return {
    headline: parts.join(", "),
    blocking: findings.filter((finding) => finding.blocking).length,
  };
}

interface AnalysisInput {
  report: LintReport | undefined;
  isFetching: boolean;
  error: Error | null;
  enabled: boolean;
}

export function analysisState({
  report,
  isFetching,
  error,
  enabled,
}: AnalysisInput): AnalysisState {
  if (!enabled) return { kind: "idle" };
  if (error) return { kind: "error", message: error.message };
  if (!report) return isFetching ? { kind: "checking" } : { kind: "idle" };

  const unrun = unrunTiers(report.tiers);
  if (report.findings.length === 0) return { kind: "clean", unrun };
  return {
    kind: "findings",
    findings: report.findings,
    summary: summarize(report.findings),
    unrun,
  };
}

/** Return the character offset at which a one-based line starts. */
export function lineOffset(source: string, line: number): number {
  if (line <= 1) return 0;
  let offset = 0;
  for (let current = 1; current < line; current += 1) {
    const next = source.indexOf("\n", offset);
    if (next === -1) return offset;
    offset = next + 1;
  }
  return offset;
}
