// Domain model for the reproducibility threat report produced by the backend
// evaluate run (api/src/repo2ree_api/evaluate.py -> core reproducibility_report.py).
// Field names mirror the camelCase JSON the backend serializes.

import type { AxisKey } from "./axes";

export type ThreatSeverity = "high" | "medium" | "low";
// Dependency declaration, environment capture, and machine (VM) capture are
// scored on independent axes (see axes.ts).
export type ThreatCategory = AxisKey;

export interface Threat {
  id: string;
  category: ThreatCategory;
  severity: ThreatSeverity;
  blocking: boolean;
  title: string;
  detail: string;
  remediation: string;
  affected: string[];
}

export interface DependencySummary {
  manifests: number;
  total: number;
  pinned: number;
  ranged: number;
  unpinned: number;
  locked: number;
}

export interface ReproducibilityReport {
  dependencyLevel: number;
  dependencyLevelLabel: string;
  environmentLevel: number;
  environmentLevelLabel: string;
  machineLevel: number;
  machineLevelLabel: string;
  dependencySummary: DependencySummary;
  threats: Threat[];
}

const SEVERITIES: readonly ThreatSeverity[] = ["high", "medium", "low"];
const CATEGORIES: readonly ThreatCategory[] = ["dependency", "environment", "machine"];

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function asInt(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.trunc(value) : 0;
}

function parseThreat(value: unknown): Threat | null {
  const raw = asRecord(value);
  if (!raw) return null;
  const id = typeof raw.id === "string" ? raw.id : null;
  const category = raw.category as ThreatCategory;
  const severity = raw.severity as ThreatSeverity;
  if (!id || !CATEGORIES.includes(category) || !SEVERITIES.includes(severity)) return null;
  return {
    id,
    category,
    severity,
    blocking: raw.blocking === true,
    title: typeof raw.title === "string" ? raw.title : "",
    detail: typeof raw.detail === "string" ? raw.detail : "",
    remediation: typeof raw.remediation === "string" ? raw.remediation : "",
    affected: Array.isArray(raw.affected)
      ? raw.affected.filter((a): a is string => typeof a === "string")
      : [],
  };
}

function parseDependencySummary(value: unknown): DependencySummary {
  const raw = asRecord(value) ?? {};
  return {
    manifests: asInt(raw.manifests),
    total: asInt(raw.total),
    pinned: asInt(raw.pinned),
    ranged: asInt(raw.ranged),
    unpinned: asInt(raw.unpinned),
    locked: asInt(raw.locked),
  };
}

/**
 * Defensively parse a raw report payload (e.g. from the API) into a typed report.
 * Returns null when the payload is not a usable report. Pure.
 */
export function parseReproducibilityReport(value: unknown): ReproducibilityReport | null {
  const raw = asRecord(value);
  if (
    !raw ||
    typeof raw.dependencyLevel !== "number" ||
    typeof raw.environmentLevel !== "number" ||
    typeof raw.machineLevel !== "number"
  ) {
    return null;
  }
  const threats = Array.isArray(raw.threats)
    ? raw.threats.map(parseThreat).filter((t): t is Threat => t !== null)
    : [];
  return {
    dependencyLevel: asInt(raw.dependencyLevel),
    dependencyLevelLabel:
      typeof raw.dependencyLevelLabel === "string" ? raw.dependencyLevelLabel : "",
    environmentLevel: asInt(raw.environmentLevel),
    environmentLevelLabel:
      typeof raw.environmentLevelLabel === "string" ? raw.environmentLevelLabel : "",
    machineLevel: asInt(raw.machineLevel),
    machineLevelLabel: typeof raw.machineLevelLabel === "string" ? raw.machineLevelLabel : "",
    dependencySummary: parseDependencySummary(raw.dependencySummary),
    threats,
  };
}
