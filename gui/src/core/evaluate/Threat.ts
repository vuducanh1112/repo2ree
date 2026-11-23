import type { AxisKey } from "./axes";

export type ThreatSeverity = "high" | "medium" | "low";
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

export const DEPENDENCY_ECOSYSTEMS = ["pypi", "conda", "npm", "apt", "oci", "other"] as const;
export type DependencyEcosystem = (typeof DEPENDENCY_ECOSYSTEMS)[number];

export const DEPENDENCY_STATUSES = [
  "locked",
  "pinned",
  "ranged",
  "unpinned",
  "undeclared",
] as const;
export type DependencyStatus = (typeof DEPENDENCY_STATUSES)[number];

export const EXPERIMENT_ENVIRONMENT_PRESENCES = [
  "observed",
  "version-mismatch",
  "not-observed",
] as const;
export type ExperimentEnvironmentPresence = (typeof EXPERIMENT_ENVIRONMENT_PRESENCES)[number];

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
  observedVersion: string | null;
  status: DependencyStatus;
  experimentEnvironmentPresence: ExperimentEnvironmentPresence | null;
}

export interface UndeclaredPackage {
  ecosystem: string;
  name: string;
  version: string | null;
}

export interface SbomCrossCheckSummary {
  sbomDigest: string | null;
  checkedAt: string;
  declaredDirectTotal: number;
  observedMatched: number;
  versionMismatches: number;
  undeclaredSameEcosystem: number;
  observedTotal: number;
  undeclared: UndeclaredPackage[];
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
  sbomCrossCheck: SbomCrossCheckSummary | null;
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
  if (!DEPENDENCY_STATUSES.includes(raw.status as DependencyStatus)) return null;
  return {
    ecosystem: raw.ecosystem as DependencyEcosystem,
    name: raw.name,
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
    observedVersion: typeof raw.observed_version === "string" ? raw.observed_version : null,
    status: raw.status as DependencyStatus,
    experimentEnvironmentPresence: EXPERIMENT_ENVIRONMENT_PRESENCES.includes(
      raw.experiment_environment_presence as ExperimentEnvironmentPresence,
    )
      ? (raw.experiment_environment_presence as ExperimentEnvironmentPresence)
      : null,
  };
}

function parseUndeclaredPackage(value: unknown): UndeclaredPackage | null {
  const raw = asRecord(value);
  if (!raw || typeof raw.name !== "string" || typeof raw.ecosystem !== "string") return null;
  return {
    ecosystem: raw.ecosystem,
    name: raw.name,
    version: typeof raw.version === "string" ? raw.version : null,
  };
}

export function parseSbomCrossCheck(value: unknown): SbomCrossCheckSummary | null {
  const raw = asRecord(value);
  if (!raw) return null;
  return {
    sbomDigest: typeof raw.sbom_digest === "string" ? raw.sbom_digest : null,
    checkedAt: typeof raw.checked_at === "string" ? raw.checked_at : "",
    declaredDirectTotal: asInt(raw.declared_direct_total),
    observedMatched: asInt(raw.observed_matched),
    versionMismatches: asInt(raw.version_mismatches),
    undeclaredSameEcosystem: asInt(raw.undeclared_same_ecosystem),
    observedTotal: asInt(raw.observed_total),
    undeclared: Array.isArray(raw.undeclared)
      ? raw.undeclared
          .map(parseUndeclaredPackage)
          .filter((pkg): pkg is UndeclaredPackage => pkg !== null)
      : [],
  };
}

export function parseReproducibilityReport(value: unknown): ReproducibilityReport | null {
  const raw = asRecord(value);
  if (
    !raw ||
    typeof raw.dependency_level !== "number" ||
    typeof raw.environment_level !== "number" ||
    typeof raw.machine_level !== "number"
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
    dependencyLevel: asInt(raw.dependency_level),
    dependencyLevelLabel:
      typeof raw.dependency_level_label === "string" ? raw.dependency_level_label : "",
    environmentLevel: asInt(raw.environment_level),
    environmentLevelLabel:
      typeof raw.environment_level_label === "string" ? raw.environment_level_label : "",
    machineLevel: asInt(raw.machine_level),
    machineLevelLabel: typeof raw.machine_level_label === "string" ? raw.machine_level_label : "",
    dependencySummary: parseDependencySummary(raw.dependency_summary),
    dependencies,
    sbomCrossCheck: parseSbomCrossCheck(raw.sbom_cross_check),
    threats,
  };
}
