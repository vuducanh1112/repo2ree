import { describe, expect, it } from "vitest";
import { isTerminalReeRunFailure, isTerminalReeRunStatus } from "./ReeRunStatus";

describe("isTerminalReeRunStatus", () => {
  it("flags the statuses a run stops at", () => {
    expect(isTerminalReeRunStatus("succeeded")).toBe(true);
    expect(isTerminalReeRunStatus("failed")).toBe(true);
    expect(isTerminalReeRunStatus("canceled")).toBe(true);
  });

  it("does not flag a run still moving", () => {
    expect(isTerminalReeRunStatus("created")).toBe(false);
    expect(isTerminalReeRunStatus("queued")).toBe(false);
    expect(isTerminalReeRunStatus("provisioning")).toBe(false);
    expect(isTerminalReeRunStatus("running")).toBe(false);
    // Cancellation has been requested but the run has not stopped yet.
    expect(isTerminalReeRunStatus("canceling")).toBe(false);
    expect(isTerminalReeRunStatus(undefined)).toBe(false);
  });
});

describe("isTerminalReeRunFailure", () => {
  it("flags failure terminal statuses", () => {
    expect(isTerminalReeRunFailure("failed")).toBe(true);
    expect(isTerminalReeRunFailure("canceled")).toBe(true);
    expect(isTerminalReeRunFailure("succeeded")).toBe(false);
  });
});
