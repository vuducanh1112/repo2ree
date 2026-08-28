import type { LintFinding, LintReport, LintTierStatus } from "@shell/infra/api/apiTypes";
import { describe, expect, it } from "vitest";
import { analysisState, findingTone, lineOffset, summarize, unrunTiers } from "./findings";

function finding(overrides: Partial<LintFinding> = {}): LintFinding {
  return {
    code: "unedited_placeholder",
    tier: "contract",
    severity: "warning",
    blocking: false,
    message: "A placeholder is still in place.",
    path: "ree-scripts/build_script.sh",
    ...overrides,
  } as LintFinding;
}

function report(overrides: Partial<LintReport> = {}): LintReport {
  return {
    schema_version: 1,
    engine_version: "1",
    target: { kind: "build", path: "ree-scripts/build_script.sh" },
    findings: [],
    tiers: [{ tier: "contract", status: "ran" }],
    ...overrides,
  } as LintReport;
}

describe("findingTone", () => {
  it.each([
    ["error", "error"],
    ["warning", "warn"],
    ["info", "info"],
  ])("reads %s as %s", (severity, tone) => {
    expect(findingTone(severity as LintFinding["severity"])).toBe(tone);
  });
});

describe("summarize", () => {
  it("counts each severity and pluralizes it", () => {
    const summary = summarize([
      finding({ severity: "error", blocking: true }),
      finding({ severity: "warning" }),
      finding({ severity: "warning" }),
      finding({ severity: "info" }),
    ]);
    expect(summary.headline).toBe("1 error, 2 warnings, 1 note");
  });

  it("counts only findings that stop the script running as blocking", () => {
    const summary = summarize([finding({ severity: "error", blocking: true }), finding()]);
    expect(summary.blocking).toBe(1);
  });

  it("names only the severities that occurred", () => {
    expect(summarize([finding()]).headline).toBe("1 warning");
  });
});

describe("unrunTiers", () => {
  it("keeps the tiers that did not run", () => {
    const tiers: LintTierStatus[] = [
      { tier: "contract", status: "ran" },
      { tier: "shell", status: "unavailable", detail: "shellcheck is not installed on this bench" },
    ];
    expect(unrunTiers(tiers).map((tier) => tier.tier)).toEqual(["shell"]);
  });
});

describe("analysisState", () => {
  const base = { report: undefined, isFetching: false, error: null, enabled: true };

  it("says nothing when checks are not enabled", () => {
    expect(analysisState({ ...base, enabled: false }).kind).toBe("idle");
  });

  it("reports a failure to check rather than a clean script", () => {
    const state = analysisState({ ...base, error: new Error("offline") });
    expect(state).toEqual({ kind: "error", message: "offline" });
  });

  it("is checking while the first report is in flight", () => {
    expect(analysisState({ ...base, isFetching: true }).kind).toBe("checking");
  });

  it("is idle before anything has been asked", () => {
    expect(analysisState(base).kind).toBe("idle");
  });

  it("carries the unrun tiers through a clean report", () => {
    // "Nothing found" and "nothing looked" must never read the same.
    const state = analysisState({
      ...base,
      report: report({ tiers: [{ tier: "shell", status: "unavailable" }] }),
    });
    expect(state).toMatchObject({ kind: "clean" });
    if (state.kind !== "clean") throw new Error("expected clean");
    expect(state.unrun).toHaveLength(1);
  });

  it("summarizes a report that found something", () => {
    const state = analysisState({ ...base, report: report({ findings: [finding()] }) });
    if (state.kind !== "findings") throw new Error("expected findings");
    expect(state.summary.headline).toBe("1 warning");
    expect(state.findings).toHaveLength(1);
  });

  it("keeps showing a stale report while the next check runs", () => {
    // Blanking the panel mid-keystroke reads as "your finding went away".
    const state = analysisState({
      ...base,
      report: report({ findings: [finding()] }),
      isFetching: true,
    });
    expect(state.kind).toBe("findings");
  });
});

describe("lineOffset", () => {
  const source = "one\ntwo\nthree\n";

  it.each([
    [1, 0],
    [2, 4],
    [3, 8],
  ])("locates line %i at offset %i", (line, offset) => {
    expect(lineOffset(source, line)).toBe(offset);
  });

  it("treats a line before the first as the start", () => {
    expect(lineOffset(source, 0)).toBe(0);
  });

  it("lands on the last line when the line no longer exists", () => {
    expect(lineOffset("one\ntwo", 99)).toBe(4);
  });
});
