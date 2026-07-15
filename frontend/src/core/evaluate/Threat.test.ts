import { describe, expect, it } from "vitest";
import { parseReproducibilityReport } from "./Threat";

describe("parseReproducibilityReport", () => {
  it("returns null for non-report payloads", () => {
    expect(parseReproducibilityReport(null)).toBeNull();
    expect(parseReproducibilityReport({})).toBeNull();
    expect(parseReproducibilityReport({ dependencyLevel: "x" })).toBeNull();
    // all three axes are required
    expect(parseReproducibilityReport({ dependencyLevel: 2, environmentLevel: 0 })).toBeNull();
  });

  it("parses a well-formed report and drops malformed threats", () => {
    const report = parseReproducibilityReport({
      dependencyLevel: 2,
      dependencyLevelLabel: "Pinned",
      environmentLevel: 0,
      environmentLevelLabel: "None",
      machineLevel: 0,
      machineLevelLabel: "None",
      ladderLevel: 3,
      ladderLabel: "Top-level Pins",
      dependencySummary: { manifests: 1, total: 2, pinned: 2, ranged: 0, unpinned: 0, locked: 0 },
      dependencies: [
        {
          ecosystem: "npm",
          name: "react",
          direct: true,
          declared_constraint: "^18.3.0",
          declared_in: "package.json",
          locked_version: "18.3.1",
          locked_hashes: ["sha512-example"],
          locked_in: "package-lock.json",
          status: "locked",
        },
        { ecosystem: "invalid", name: "ignored", status: "locked" },
        // A row without a valid backend-computed status is unusable.
        { ecosystem: "npm", name: "no-status", direct: true },
        { ecosystem: "npm", name: "bad-status", direct: true, status: "shiny" },
      ],
      threats: [
        {
          id: "no-lockfile",
          category: "dependency",
          severity: "medium",
          blocking: true,
          title: "No lockfile",
          detail: "…",
          remediation: "Use a lockfile.",
          affected: ["requirements.txt", 42],
        },
        { id: "bogus", category: "nonsense", severity: "medium" },
      ],
    });

    expect(report).not.toBeNull();
    expect(report?.dependencyLevel).toBe(2);
    expect(report?.environmentLevel).toBe(0);
    expect(report?.machineLevel).toBe(0);
    expect(report?.threats).toHaveLength(1);
    expect(report?.threats[0].blocking).toBe(true);
    expect(report?.threats[0].affected).toEqual(["requirements.txt"]);
    expect(report?.dependencySummary.pinned).toBe(2);
    expect(report?.dependencies).toEqual([
      expect.objectContaining({
        ecosystem: "npm",
        name: "react",
        lockedVersion: "18.3.1",
        status: "locked",
      }),
    ]);
  });

  it("defaults a missing threats array to empty", () => {
    const report = parseReproducibilityReport({
      dependencyLevel: 0,
      environmentLevel: 0,
      machineLevel: 0,
    });
    expect(report?.threats).toEqual([]);
    expect(report?.sbomCrossCheck).toBeNull();
  });

  it("parses cross-check enrichment: presence, undeclared rows, and the summary", () => {
    const report = parseReproducibilityReport({
      dependencyLevel: 3,
      environmentLevel: 0,
      machineLevel: 0,
      dependencies: [
        {
          ecosystem: "pypi",
          name: "requests",
          direct: true,
          declared_in: "requirements.txt",
          locked_version: "2.31.0",
          observed_version: "2.31.0",
          status: "locked",
          runtime_presence: "observed",
        },
        {
          ecosystem: "pypi",
          name: "certifi",
          direct: false,
          observed_version: "2024.2.2",
          status: "undeclared",
          // An unknown presence value degrades to null, not a dropped row.
          runtime_presence: "shiny",
        },
      ],
      sbomCrossCheck: {
        sbomDigest: "sha256:abc",
        checkedAt: "2026-07-15T00:00:00Z",
        declaredDirectTotal: 1,
        observedMatched: 1,
        versionMismatches: 0,
        undeclaredSameEcosystem: 1,
        observedTotal: 42,
        undeclared: [{ ecosystem: "pypi", name: "certifi", version: "2024.2.2" }, { bad: true }],
      },
      threats: [],
    });

    expect(report?.dependencies).toEqual([
      expect.objectContaining({
        name: "requests",
        observedVersion: "2.31.0",
        runtimePresence: "observed",
      }),
      expect.objectContaining({ name: "certifi", status: "undeclared", runtimePresence: null }),
    ]);
    expect(report?.sbomCrossCheck).toEqual(
      expect.objectContaining({
        declaredDirectTotal: 1,
        observedMatched: 1,
        undeclaredSameEcosystem: 1,
        observedTotal: 42,
        undeclared: [{ ecosystem: "pypi", name: "certifi", version: "2024.2.2" }],
      }),
    );
  });
});
