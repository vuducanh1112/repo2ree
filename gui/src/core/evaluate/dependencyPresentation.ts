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

// How each of these reads is keyed off the identity itself in the shell
// (theme/tones.css); what core owns is the wording.

export const ECO_LABEL: Record<DependencyEcosystem, string> = {
  pypi: "PyPI",
  conda: "conda",
  npm: "npm",
  apt: "apt",
  oci: "OCI",
  other: "other",
};

export const STATUS_LABEL: Record<DependencyStatus, string> = {
  locked: "locked",
  pinned: "pinned",
  ranged: "range",
  unpinned: "unpinned",
  undeclared: "undeclared",
};

export const PRESENCE_LABEL: Record<RuntimePresence, string> = {
  observed: "in runtime",
  "version-mismatch": "version mismatch",
  "not-observed": "not in runtime",
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
