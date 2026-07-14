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

// Single source for the ecosystem members: the type union, the runtime parse
// guard, and presentation tables all derive from this tuple, so adding an
// ecosystem is one edit (plus the backend Literal in domain/dependency.py).
export const DEPENDENCY_ECOSYSTEMS = ["pypi", "conda", "npm", "apt", "oci", "other"] as const;
export type DependencyEcosystem = (typeof DEPENDENCY_ECOSYSTEMS)[number];

// Per-row reproducibility rung, computed by the backend's single classifier
// (reproducibility_report._dependency_status) — never re-derived client-side.
export const DEPENDENCY_STATUSES = ["locked", "pinned", "ranged", "unpinned"] as const;
export type DependencyStatus = (typeof DEPENDENCY_STATUSES)[number];

/** A normalized row emitted by the backend manifest scan. */
export interface EvaluatedDependency {
  ecosystem: DependencyEcosystem;
  name: string;
  nameAsWritten: string | null;
  scope: string | null;
  direct: boolean;
  declaredConstraint: string | null;
  declaredIn: string | null;
  lockedVersion: string | null;
  lockedHashes: string[];
  lockedIn: string | null;
  status: DependencyStatus;
}

export interface ReproducibilityReport {
  dependencyLevel: number;
  dependencyLevelLabel: string;
  environmentLevel: number;
  environmentLevelLabel: string;
  machineLevel: number;
  machineLevelLabel: string;
  dependencySummary: DependencySummary;
  dependencies: EvaluatedDependency[];
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

function parseDependency(value: unknown): EvaluatedDependency | null {
  const raw = asRecord(value);
  if (!raw || typeof raw.name !== "string" || typeof raw.ecosystem !== "string") return null;
  if (!DEPENDENCY_ECOSYSTEMS.includes(raw.ecosystem as DependencyEcosystem)) return null;
  // A row without a valid backend-computed status is unusable (pre-status
  // reports regenerate on the next evaluate run) — drop it rather than guess.
  if (!DEPENDENCY_STATUSES.includes(raw.status as DependencyStatus)) return null;
  return {
    ecosystem: raw.ecosystem as DependencyEcosystem,
    name: raw.name,
    // Dependency is a core-domain model (snake_case); the report envelope is
    // camelCase. Normalize that embedded shape at the frontend boundary.
    nameAsWritten: typeof raw.name_as_written === "string" ? raw.name_as_written : null,
    scope: typeof raw.scope === "string" ? raw.scope : null,
    direct: raw.direct !== false,
    declaredConstraint:
      typeof raw.declared_constraint === "string" ? raw.declared_constraint : null,
    declaredIn: typeof raw.declared_in === "string" ? raw.declared_in : null,
    lockedVersion: typeof raw.locked_version === "string" ? raw.locked_version : null,
    lockedHashes: Array.isArray(raw.locked_hashes)
      ? raw.locked_hashes.filter((hash): hash is string => typeof hash === "string")
      : [],
    lockedIn: typeof raw.locked_in === "string" ? raw.locked_in : null,
    status: raw.status as DependencyStatus,
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
  const dependencies = Array.isArray(raw.dependencies)
    ? raw.dependencies
        .map(parseDependency)
        .filter((dependency): dependency is EvaluatedDependency => dependency !== null)
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
    dependencies,
    threats,
  };
}
