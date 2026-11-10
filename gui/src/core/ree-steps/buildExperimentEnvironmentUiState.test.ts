import { describe, expect, it } from "vitest";
import {
  buildFooterHint,
  buildReadiness,
  buildRunStatusLabel,
  buildSummaryStatusLabel,
  canRunBuild,
  deriveExperimentEnvironmentFileSize,
  experimentEnvironmentArtifactStatus,
  experimentEnvironmentArtifactStatusLabel,
  experimentEnvironmentSummaryStatusLabel,
} from "./buildExperimentEnvironmentUiState";

describe("buildRunStatusLabel", () => {
  const idle = { running: false, runFailed: false };
  it("running wins", () => {
    expect(
      buildRunStatusLabel({ running: true, runDone: true, runFailed: false, hasScript: true }),
    ).toBe("Building");
  });
  it("runDone -> Built", () => {
    expect(buildRunStatusLabel({ ...idle, runDone: true, hasScript: false })).toBe("Built");
  });
  it("failed run -> Build failed, not Built", () => {
    expect(
      buildRunStatusLabel({ running: false, runDone: true, runFailed: true, hasScript: true }),
    ).toBe("Build failed");
  });
  it("hasScript -> Ready", () => {
    expect(buildRunStatusLabel({ ...idle, runDone: false, hasScript: true })).toBe("Ready");
  });
  it("reserved script means idle build is ready", () => {
    expect(buildRunStatusLabel({ ...idle, runDone: false, hasScript: false })).toBe("Ready");
  });
});

describe("experimentEnvironmentArtifactStatus", () => {
  const base = { hasExperimentEnvironment: true, experimentEnvironmentPathExists: true };
  it("undeclared when no experiment environment path is authored", () => {
    expect(experimentEnvironmentArtifactStatus({ ...base, hasExperimentEnvironment: false })).toBe(
      "undeclared",
    );
  });
  it("declared — not missing — when the build has not produced it yet", () => {
    expect(
      experimentEnvironmentArtifactStatus({ ...base, experimentEnvironmentPathExists: false }),
    ).toBe("declared");
  });
  it("produced when present in workspace", () => {
    expect(experimentEnvironmentArtifactStatus(base)).toBe("produced");
  });
  it("has UI labels", () => {
    expect(experimentEnvironmentArtifactStatusLabel("undeclared")).toBe("Not declared");
    expect(experimentEnvironmentArtifactStatusLabel("declared")).toBe("Awaiting build");
    expect(experimentEnvironmentArtifactStatusLabel("produced")).toBe("Built");
    expect(experimentEnvironmentSummaryStatusLabel("produced")).toBe("In workspace");
    expect(experimentEnvironmentSummaryStatusLabel("declared")).toBe("Declared, not built");
  });
});

describe("canRunBuild", () => {
  const ready = {
    running: false,
    hasMissing: false,
    hasScript: true,
    hasExperimentEnvironmentPath: true,
  };
  it("runs when the script and the declared experiment environment path are both there", () => {
    expect(canRunBuild(ready)).toBe(true);
  });
  it("refuses without a declared experiment environment path", () => {
    expect(canRunBuild({ ...ready, hasExperimentEnvironmentPath: false })).toBe(false);
  });
  it("refuses while running, missing inputs, or without a script", () => {
    expect(canRunBuild({ ...ready, running: true })).toBe(false);
    expect(canRunBuild({ ...ready, hasMissing: true })).toBe(false);
    expect(canRunBuild({ ...ready, hasScript: false })).toBe(false);
  });
});

describe("buildFooterHint / summary", () => {
  const declared = { hasExperimentEnvironmentPath: true };
  it("does not expose an add-script state", () => {
    expect(
      buildFooterHint({ ...declared, runDone: false, runFailed: false, hasScript: false }),
    ).toContain("Script ready");
  });
  it("invites run when script ready", () => {
    expect(
      buildFooterHint({ ...declared, runDone: false, runFailed: false, hasScript: true }),
    ).toContain("Script ready");
  });
  it("asks for the experiment environment path before the run", () => {
    expect(
      buildFooterHint({
        runDone: false,
        runFailed: false,
        hasScript: true,
        hasExperimentEnvironmentPath: false,
      }),
    ).toContain("Declare where the build writes the experiment environment");
  });
  it("invites sbom after build", () => {
    expect(
      buildFooterHint({ ...declared, runDone: true, runFailed: false, hasScript: true }),
    ).toContain("SBOM");
  });
  it("points at the log after a failed build", () => {
    expect(
      buildFooterHint({
        runDone: true,
        runFailed: true,
        hasScript: true,
        hasExperimentEnvironmentPath: false,
      }),
    ).toContain("Build failed");
  });
  it("summary label tracks state", () => {
    expect(buildSummaryStatusLabel({ runDone: true, hasScript: true })).toBe("Built");
    expect(buildSummaryStatusLabel({ runDone: false, hasScript: true })).toBe("Ready");
    expect(buildSummaryStatusLabel({ runDone: false, hasScript: false })).toBe("Ready");
  });
});

describe("buildReadiness", () => {
  it("empty state is 0%", () => {
    const r = buildReadiness({
      hasScript: false,
      hasExperimentEnvironment: false,
      experimentEnvironmentPathExists: false,
      runDone: false,
    });
    expect(r).toMatchObject({ done: 0, total: 3, percent: 0, experimentEnvironmentReady: false });
  });
  it("script only is 33%", () => {
    const r = buildReadiness({
      hasScript: true,
      hasExperimentEnvironment: false,
      experimentEnvironmentPathExists: false,
      runDone: false,
    });
    expect(r.percent).toBe(33);
  });
  it("experiment environment path missing does not count", () => {
    const r = buildReadiness({
      hasScript: true,
      hasExperimentEnvironment: true,
      experimentEnvironmentPathExists: false,
      runDone: false,
    });
    expect(r.experimentEnvironmentReady).toBe(false);
    expect(r.done).toBe(1);
  });
  it("everything done is 100%", () => {
    const r = buildReadiness({
      hasScript: true,
      hasExperimentEnvironment: true,
      experimentEnvironmentPathExists: true,
      runDone: true,
    });
    expect(r).toMatchObject({ done: 3, percent: 100, experimentEnvironmentReady: true });
  });
});

describe("deriveExperimentEnvironmentFileSize", () => {
  it("returns null for missing file", () => {
    expect(deriveExperimentEnvironmentFileSize(null)).toBeNull();
  });
  it("uses explicit size when positive", () => {
    expect(deriveExperimentEnvironmentFileSize({ size: 2048 })).toBe("2.0 KB");
  });
  it("falls back to size match in content", () => {
    expect(deriveExperimentEnvironmentFileSize({ content: "Size: ~3.5 MB" })).toBe("~3.5 MB");
  });
  it("computes byte length when no other hint", () => {
    expect(deriveExperimentEnvironmentFileSize({ content: "hi" })).toBe("2 B");
  });
});
