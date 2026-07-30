import { describe, expect, it } from "vitest";
import { cancelFailureMessage, cancelSuccessMessage, planCancelRequest } from "./cancelPlan";

describe("cancelPlan", () => {
  it("plans a cancel request when a run is active", () => {
    expect(planCancelRequest("run-7")).toEqual({ runId: "run-7" });
  });

  it("plans nothing when no run is active", () => {
    expect(planCancelRequest(undefined)).toBeNull();
  });

  it("builds a user-facing success message", () => {
    expect(cancelSuccessMessage("source")).toBe("Cancel requested for source");
  });

  it("builds a user-facing failure message from an error", () => {
    expect(cancelFailureMessage("build", new Error("network down"))).toBe(
      "Failed to cancel build: network down",
    );
  });

  it("falls back to a generic failure message for non-errors", () => {
    expect(cancelFailureMessage("build", "boom")).toBe("Failed to cancel build");
  });
});
