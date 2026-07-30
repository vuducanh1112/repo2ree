import { describe, expect, it } from "vitest";
import type { ReeRunFailure } from "./ReeRun";
import { runFailurePresentation } from "./runFailurePresentation";

function failure(overrides: Partial<ReeRunFailure> = {}): ReeRunFailure {
  return {
    category: "execution",
    message: "boom",
    retryable: false,
    origin: "core",
    ...overrides,
  };
}

describe("runFailurePresentation", () => {
  it("labels an execution failure as a fault", () => {
    const view = runFailurePresentation(failure({ category: "execution" }));
    expect(view.tone).toBe("fault");
    expect(view.label).toBe("Run failed");
  });

  it("treats an unavailable workbench as a transient failure", () => {
    const view = runFailurePresentation(failure({ category: "unavailable" }));
    expect(view.tone).toBe("transient");
    expect(view.label).toBe("Workbench unavailable");
  });

  it("treats validation and conflict as rejected, not faults", () => {
    expect(runFailurePresentation(failure({ category: "validation" })).tone).toBe("rejected");
    expect(runFailurePresentation(failure({ category: "conflict" })).tone).toBe("rejected");
  });

  it("carries through the backend's explicit retryable signal", () => {
    expect(runFailurePresentation(failure({ retryable: true })).retryable).toBe(true);
    expect(runFailurePresentation(failure({ retryable: false })).retryable).toBe(false);
  });

  it("passes the underlying message through for detail display", () => {
    expect(runFailurePresentation(failure({ message: "no space left" })).message).toBe(
      "no space left",
    );
  });
});
