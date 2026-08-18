import { describe, expect, it } from "vitest";
import { groupEvaluatedDependencies, tallyByStatus } from "./dependencyPresentation";
import type { EvaluatedDependency } from "./Threat";

function dependency(overrides: Partial<EvaluatedDependency> = {}): EvaluatedDependency {
  return {
    ecosystem: "pypi",
    name: "normalized",
    nameAsWritten: "WrittenName",
    scope: "runtime",
    direct: true,
    declaredConstraint: ">=1",
    declaredIn: "requirements.txt",
    lockedVersion: "1.2.3",
    lockedHashes: [],
    lockedIn: null,
    observedVersion: null,
    status: "locked",
    runtimePresence: null,
    ...overrides,
  };
}

describe("dependency presentation", () => {
  it("groups direct declared packages and preserves preferred display values", () => {
    const groups = groupEvaluatedDependencies([
      dependency(),
      dependency({ name: "second", nameAsWritten: null, lockedVersion: null, status: "ranged" }),
    ]);
    expect(groups).toEqual([
      {
        path: "requirements.txt",
        ecosystem: "pypi",
        packages: [
          expect.objectContaining({ name: "WrittenName", version: "1.2.3", status: "locked" }),
          expect.objectContaining({ name: "second", version: ">=1", status: "ranged" }),
        ],
      },
    ]);
  });

  it("separates ecosystems and ignores transitive, OCI, and undeclared rows", () => {
    const groups = groupEvaluatedDependencies([
      dependency({ direct: false }),
      dependency({ ecosystem: "oci" }),
      dependency({ declaredIn: null }),
      dependency({ ecosystem: "npm", declaredIn: "package.json", name: "react" }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({ path: "package.json", ecosystem: "npm" });
  });

  it("tallies every dependency status", () => {
    expect(
      tallyByStatus([
        {
          name: "a",
          version: null,
          status: "locked",
          scope: null,
          runtimePresence: null,
          observedVersion: null,
        },
        {
          name: "b",
          version: null,
          status: "pinned",
          scope: null,
          runtimePresence: null,
          observedVersion: null,
        },
        {
          name: "c",
          version: null,
          status: "ranged",
          scope: null,
          runtimePresence: null,
          observedVersion: null,
        },
        {
          name: "d",
          version: null,
          status: "unpinned",
          scope: null,
          runtimePresence: null,
          observedVersion: null,
        },
        {
          name: "e",
          version: null,
          status: "undeclared",
          scope: null,
          runtimePresence: null,
          observedVersion: null,
        },
      ]),
    ).toEqual({ locked: 1, pinned: 1, ranged: 1, unpinned: 1, undeclared: 1, total: 5 });
  });
});
