import { describe, expect, it } from "vitest";
import {
  activationFooterHint,
  activationReadiness,
  activationRunLabel,
  canRunActivation,
} from "./activationUiState";

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
    runDone: false,
  };
  it("empty state is 0%", () => {
    const r = activationReadiness(empty);
    expect(r).toMatchObject({ done: 0, total: 3, percent: 0 });
  });
  it("runtime configured counts as 1", () => {
    const r = activationReadiness({ ...empty, hasRuntime: true });
    expect(r.done).toBe(1);
    expect(r.percent).toBe(33);
  });
  it("fully ready is 100%", () => {
    const r = activationReadiness({
      hasRuntime: true,
      runtimePathExists: true,
      runDone: true,
    });
    expect(r).toMatchObject({ done: 3, total: 3, percent: 100 });
  });
});
