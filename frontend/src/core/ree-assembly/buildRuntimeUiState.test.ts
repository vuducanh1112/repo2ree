import { describe, expect, it } from "vitest";
import {
  buildFooterHint,
  buildReadiness,
  buildRunStatusLabel,
  buildSummaryStatusLabel,
  deriveRuntimeFileSize,
  runtimeArtifactStatus,
  runtimeArtifactStatusLabel,
  runtimeSummaryStatusLabel,
} from "./buildRuntimeUiState";

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

describe("runtimeArtifactStatus", () => {
  const base = { hasRuntime: true, runtimePathExists: true };
  it("unset when no runtime", () => {
    expect(runtimeArtifactStatus({ ...base, hasRuntime: false })).toBe("unset");
  });
  it("missing when path not in workspace", () => {
    expect(runtimeArtifactStatus({ ...base, runtimePathExists: false })).toBe("missing");
  });
  it("ready when present in workspace", () => {
    expect(runtimeArtifactStatus(base)).toBe("ready");
  });
  it("has UI labels", () => {
    expect(runtimeArtifactStatusLabel("unset")).toBe("Not set");
    expect(runtimeArtifactStatusLabel("missing")).toBe("Missing");
    expect(runtimeArtifactStatusLabel("ready")).toBe("Ready");
    expect(runtimeSummaryStatusLabel("ready")).toBe("In workspace");
  });
});

describe("buildFooterHint / summary", () => {
  it("does not expose an add-script state", () => {
    expect(buildFooterHint({ runDone: false, runFailed: false, hasScript: false })).toContain(
      "Script ready",
    );
  });
  it("invites run when script ready", () => {
    expect(buildFooterHint({ runDone: false, runFailed: false, hasScript: true })).toContain(
      "Script ready",
    );
  });
  it("invites sbom after build", () => {
    expect(buildFooterHint({ runDone: true, runFailed: false, hasScript: true })).toContain("SBOM");
  });
  it("points at the log after a failed build", () => {
    expect(buildFooterHint({ runDone: true, runFailed: true, hasScript: true })).toContain(
      "Build failed",
    );
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
      hasRuntime: false,
      runtimePathExists: false,
      runDone: false,
    });
    expect(r).toMatchObject({ done: 0, total: 3, percent: 0, runtimeReady: false });
  });
  it("script only is 33%", () => {
    const r = buildReadiness({
      hasScript: true,
      hasRuntime: false,
      runtimePathExists: false,
      runDone: false,
    });
    expect(r.percent).toBe(33);
  });
  it("runtime path missing does not count", () => {
    const r = buildReadiness({
      hasScript: true,
      hasRuntime: true,
      runtimePathExists: false,
      runDone: false,
    });
    expect(r.runtimeReady).toBe(false);
    expect(r.done).toBe(1);
  });
  it("everything done is 100%", () => {
    const r = buildReadiness({
      hasScript: true,
      hasRuntime: true,
      runtimePathExists: true,
      runDone: true,
    });
    expect(r).toMatchObject({ done: 3, percent: 100, runtimeReady: true });
  });
});

describe("deriveRuntimeFileSize", () => {
  it("returns null for missing file", () => {
    expect(deriveRuntimeFileSize(null)).toBeNull();
  });
  it("uses explicit size when positive", () => {
    expect(deriveRuntimeFileSize({ size: 2048 })).toBe("2.0 KB");
  });
  it("falls back to size match in content", () => {
    expect(deriveRuntimeFileSize({ content: "Size: ~3.5 MB" })).toBe("~3.5 MB");
  });
  it("computes byte length when no other hint", () => {
    expect(deriveRuntimeFileSize({ content: "hi" })).toBe("2 B");
  });
});
