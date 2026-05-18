import { describe, expect, it } from "vitest";
import {
  activationFooterHint,
  activationProvenanceLabel,
  activationReadiness,
  activationRunLabel,
  activationSourceAfterGenerate,
  activationSourceAfterSave,
  canRunActivation,
  modeForActivationSource,
} from "./activationUiState";

describe("modeForActivationSource", () => {
  it("defaults to pick when null", () => {
    expect(modeForActivationSource(null)).toBe("pick");
  });
  it("returns generate for generated source", () => {
    expect(modeForActivationSource({ kind: "generated", base: "activation-smoke" })).toBe(
      "generate",
    );
  });
  it("returns write for manual source", () => {
    expect(modeForActivationSource({ kind: "manual" })).toBe("write");
  });
  it("returns pick for picked source", () => {
    expect(modeForActivationSource({ kind: "picked" })).toBe("pick");
  });
});

describe("activationProvenanceLabel", () => {
  it("no script yet when null", () => {
    expect(activationProvenanceLabel(null)).toBe("No script yet");
  });
  it("picked from workspace", () => {
    expect(activationProvenanceLabel({ kind: "picked" })).toBe("Picked from workspace");
  });
  it("hand-written for manual", () => {
    expect(activationProvenanceLabel({ kind: "manual" })).toBe("Hand-written");
  });
  it("generated with base and edited flag", () => {
    expect(
      activationProvenanceLabel({ kind: "generated", base: "activation-smoke", edited: true }),
    ).toBe("Generated · activation-smoke · edited");
  });
});

describe("activationSourceAfterGenerate", () => {
  it("returns generated source with edited false", () => {
    expect(activationSourceAfterGenerate("activation-smoke")).toEqual({
      kind: "generated",
      base: "activation-smoke",
      edited: false,
    });
  });
});

describe("activationSourceAfterSave", () => {
  it("marks generated source as edited", () => {
    const src = activationSourceAfterGenerate("activation-smoke");
    expect(activationSourceAfterSave(src)).toMatchObject({ kind: "generated", edited: true });
  });
  it("returns manual when saving from null", () => {
    expect(activationSourceAfterSave(null)).toEqual({ kind: "manual" });
  });
  it("returns manual when saving from picked", () => {
    expect(activationSourceAfterSave({ kind: "picked" })).toEqual({ kind: "manual" });
  });
});

describe("activationRunLabel", () => {
  it("shows Testing while running", () => {
    expect(activationRunLabel({ running: true, runDone: false })).toBe("Testing...");
  });
  it("offers re-run after done", () => {
    expect(activationRunLabel({ running: false, runDone: true })).toBe("Re-run activation");
  });
  it("default is Run activation", () => {
    expect(activationRunLabel({ running: false, runDone: false })).toBe("Run activation");
  });
});

describe("canRunActivation", () => {
  const ready = {
    running: false,
    hasMissing: false,
    runtimePathExists: true,
    scriptFileMissing: false,
  };
  it("allows run when all conditions met", () => {
    expect(canRunActivation(ready)).toBe(true);
  });
  it("blocks when running", () => {
    expect(canRunActivation({ ...ready, running: true })).toBe(false);
  });
  it("blocks when missing fields", () => {
    expect(canRunActivation({ ...ready, hasMissing: true })).toBe(false);
  });
  it("blocks when runtime file absent", () => {
    expect(canRunActivation({ ...ready, runtimePathExists: false })).toBe(false);
  });
  it("blocks when script file missing from workspace", () => {
    expect(canRunActivation({ ...ready, scriptFileMissing: true })).toBe(false);
  });
});

describe("activationFooterHint", () => {
  it("congratulates on pass", () => {
    expect(activationFooterHint({ runDone: true })).toContain("Activation passed");
  });
  it("prompts to run when not done", () => {
    expect(activationFooterHint({ runDone: false })).toContain("Run the smoke test");
  });
});

describe("activationReadiness", () => {
  const empty = {
    hasRuntime: false,
    runtimePathExists: false,
    hasScript: false,
    scriptPresent: false,
    runDone: false,
  };
  it("empty state is 0%", () => {
    const r = activationReadiness(empty);
    expect(r).toMatchObject({ done: 0, total: 4, percent: 0 });
  });
  it("runtime configured counts as 1", () => {
    const r = activationReadiness({ ...empty, hasRuntime: true });
    expect(r.done).toBe(1);
    expect(r.percent).toBe(25);
  });
  it("script present requires both hasScript and scriptPresent", () => {
    expect(activationReadiness({ ...empty, hasScript: true, scriptPresent: false }).done).toBe(0);
    expect(activationReadiness({ ...empty, hasScript: true, scriptPresent: true }).done).toBe(1);
  });
  it("fully ready is 100%", () => {
    const r = activationReadiness({
      hasRuntime: true,
      runtimePathExists: true,
      hasScript: true,
      scriptPresent: true,
      runDone: true,
    });
    expect(r).toMatchObject({ done: 4, total: 4, percent: 100 });
  });
});
