import { describe, expect, it } from "vitest";
import {
  buildFooterHint,
  buildReadiness,
  buildRunStatusLabel,
  buildSummaryStatusLabel,
  deriveRuntimeFileSize,
  modeForSource,
  provenanceLabel,
  runtimeArtifactStatus,
  runtimeArtifactStatusLabel,
  runtimeSummaryStatusLabel,
  sourceAfterGenerate,
  sourceAfterSave,
} from "./buildRuntimeUiState";

describe("modeForSource", () => {
  it("defaults to pick when no source", () => {
    expect(modeForSource(null)).toBe("pick");
  });
  it("maps generated -> generate", () => {
    expect(modeForSource({ kind: "generated", base: "x" })).toBe("generate");
  });
  it("maps manual -> write", () => {
    expect(modeForSource({ kind: "manual" })).toBe("write");
  });
  it("maps picked -> pick", () => {
    expect(modeForSource({ kind: "picked" })).toBe("pick");
  });
});

describe("provenanceLabel", () => {
  it("describes empty state", () => {
    expect(provenanceLabel(null)).toBe("No script yet");
  });
  it("describes picked", () => {
    expect(provenanceLabel({ kind: "picked" })).toBe("Picked from workspace");
  });
  it("describes manual", () => {
    expect(provenanceLabel({ kind: "manual" })).toBe("Hand-written");
  });
  it("describes generated with base", () => {
    expect(provenanceLabel({ kind: "generated", base: "docker-export" })).toBe(
      "Generated · docker-export",
    );
  });
  it("flags edited generated", () => {
    expect(provenanceLabel({ kind: "generated", base: "docker-export", edited: true })).toBe(
      "Generated · docker-export · edited",
    );
  });
});

describe("source transitions", () => {
  it("sourceAfterGenerate marks not edited", () => {
    expect(sourceAfterGenerate("nix-docker")).toEqual({
      kind: "generated",
      base: "nix-docker",
      edited: false,
    });
  });
  it("sourceAfterSave forks generated into edited", () => {
    expect(sourceAfterSave({ kind: "generated", base: "x", edited: false })).toEqual({
      kind: "generated",
      base: "x",
      edited: true,
    });
  });
  it("sourceAfterSave from null is manual", () => {
    expect(sourceAfterSave(null)).toEqual({ kind: "manual" });
  });
  it("sourceAfterSave from picked is manual", () => {
    expect(sourceAfterSave({ kind: "picked" })).toEqual({ kind: "manual" });
  });
});

describe("buildRunStatusLabel", () => {
  it("running wins", () => {
    expect(buildRunStatusLabel({ running: true, runDone: true, hasScript: true })).toBe("Building");
  });
  it("runDone -> Built", () => {
    expect(buildRunStatusLabel({ running: false, runDone: true, hasScript: false })).toBe("Built");
  });
  it("hasScript -> Ready", () => {
    expect(buildRunStatusLabel({ running: false, runDone: false, hasScript: true })).toBe("Ready");
  });
  it("nothing -> Empty", () => {
    expect(buildRunStatusLabel({ running: false, runDone: false, hasScript: false })).toBe("Empty");
  });
});

describe("runtimeArtifactStatus", () => {
  const base = { hasRuntime: true, runtimePathExists: true, includeRuntime: true };
  it("unset when no runtime", () => {
    expect(runtimeArtifactStatus({ ...base, hasRuntime: false })).toBe("unset");
  });
  it("missing when path not in workspace", () => {
    expect(runtimeArtifactStatus({ ...base, runtimePathExists: false })).toBe("missing");
  });
  it("excluded when not included", () => {
    expect(runtimeArtifactStatus({ ...base, includeRuntime: false })).toBe("excluded");
  });
  it("included otherwise", () => {
    expect(runtimeArtifactStatus(base)).toBe("included");
  });
  it("has UI labels", () => {
    expect(runtimeArtifactStatusLabel("unset")).toBe("Not set");
    expect(runtimeArtifactStatusLabel("missing")).toBe("Missing");
    expect(runtimeSummaryStatusLabel("included")).toBe("Bundled in REE");
    expect(runtimeSummaryStatusLabel("excluded")).toBe("Selected · not bundled");
  });
});

describe("buildFooterHint / summary", () => {
  it("urges add when no script", () => {
    expect(buildFooterHint({ runDone: false, hasScript: false })).toContain("Add a build script");
  });
  it("invites run when script ready", () => {
    expect(buildFooterHint({ runDone: false, hasScript: true })).toContain("Script ready");
  });
  it("invites sbom after build", () => {
    expect(buildFooterHint({ runDone: true, hasScript: true })).toContain("SBOM");
  });
  it("summary label tracks state", () => {
    expect(buildSummaryStatusLabel({ runDone: true, hasScript: true })).toBe("Built");
    expect(buildSummaryStatusLabel({ runDone: false, hasScript: true })).toBe("Ready");
    expect(buildSummaryStatusLabel({ runDone: false, hasScript: false })).toBe("Empty");
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
