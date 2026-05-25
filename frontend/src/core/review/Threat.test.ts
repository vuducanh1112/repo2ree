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
  });

  it("defaults a missing threats array to empty", () => {
    const report = parseReproducibilityReport({
      dependencyLevel: 0,
      environmentLevel: 0,
      machineLevel: 0,
    });
    expect(report?.threats).toEqual([]);
  });
});
