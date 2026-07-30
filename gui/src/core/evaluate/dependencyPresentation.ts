import type {
  DependencyEcosystem,
  DependencyStatus,
  EvaluatedDependency,
  RuntimePresence,
} from "./Threat";

export interface DisplayDependency {
  name: string;
  version: string | null;
  status: DependencyStatus;
  scope: string | null;
  /** SBOM cross-check verdict; null until a cross-check ran. */
  runtimePresence: RuntimePresence | null;
  observedVersion: string | null;
}

export interface DependencyGroup {
  path: string;
  ecosystem: DependencyEcosystem;
  packages: DisplayDependency[];
}

type StatusTally = Record<DependencyStatus, number> & { total: number };

interface EcoMeta {
  label: string;
  color: string;
  bg: string;
}

interface StatusMeta {
  label: string;
  color: string;
  bg: string;
  border: string;
}

export const ECO_META: Record<DependencyEcosystem, EcoMeta> = {
  pypi: { label: "PyPI", color: "#3b82f6", bg: "#eff6ff" },
  conda: { label: "conda", color: "#22c55e", bg: "#f0fdf4" },
  npm: { label: "npm", color: "#dc2626", bg: "#fef2f2" },
  apt: { label: "apt", color: "#f59e0b", bg: "#fffbeb" },
  oci: { label: "OCI", color: "#0891b2", bg: "#ecfeff" },
  other: { label: "other", color: "#64748b", bg: "#f8fafc" },
};

export const STATUS_META: Record<DependencyStatus, StatusMeta> = {
  locked: { label: "locked", color: "#2563eb", bg: "#dbeafe", border: "#93c5fd" },
  pinned: { label: "pinned", color: "#16a34a", bg: "#dcfce7", border: "#86efac" },
  ranged: { label: "range", color: "#d97706", bg: "#fef3c7", border: "#fcd34d" },
  unpinned: { label: "unpinned", color: "#dc2626", bg: "#fef2f2", border: "#fca5a5" },
  undeclared: { label: "undeclared", color: "#9333ea", bg: "#faf5ff", border: "#d8b4fe" },
};

// Presence is evidence, not a defect scale: "not-observed" stays muted because
// dev/build-only dependencies legitimately never reach the runtime.
export const PRESENCE_META: Record<RuntimePresence, StatusMeta> = {
  observed: { label: "in runtime", color: "#16a34a", bg: "#dcfce7", border: "#86efac" },
  "version-mismatch": {
    label: "version mismatch",
    color: "#d97706",
    bg: "#fef3c7",
    border: "#fcd34d",
  },
  "not-observed": { label: "not in runtime", color: "#64748b", bg: "#f8fafc", border: "#e2e8f0" },
};

/**
 * Present the backend inventory; the status comes classified from the backend
 * and this module never re-derives it.
 */
export function groupEvaluatedDependencies(dependencies: EvaluatedDependency[]): DependencyGroup[] {
  const groups = new Map<string, DependencyGroup>();
  for (const dependency of dependencies) {
    if (!dependency.direct || dependency.ecosystem === "oci" || !dependency.declaredIn) continue;
    const key = `${dependency.declaredIn}\u0000${dependency.ecosystem}`;
    const group = groups.get(key) ?? {
      path: dependency.declaredIn,
      ecosystem: dependency.ecosystem,
      packages: [],
    };
    group.packages.push({
      name: dependency.nameAsWritten ?? dependency.name,
      version: dependency.lockedVersion ?? dependency.declaredConstraint,
      status: dependency.status,
      scope: dependency.scope,
      runtimePresence: dependency.runtimePresence,
      observedVersion: dependency.observedVersion,
    });
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** One pass over the packages; the single definition of every status count. */
export function tallyByStatus(packages: Iterable<DisplayDependency>): StatusTally {
  const tally: StatusTally = {
    locked: 0,
    pinned: 0,
    ranged: 0,
    unpinned: 0,
    undeclared: 0,
    total: 0,
  };
  for (const pkg of packages) {
    tally[pkg.status] += 1;
    tally.total += 1;
  }
  return tally;
}
