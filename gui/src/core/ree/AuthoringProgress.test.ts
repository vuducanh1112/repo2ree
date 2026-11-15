import { describe, expect, it } from "vitest";
import { isAuthoringStepComplete, mapRawAuthoringProgress } from "./AuthoringProgress";

describe("authoring progress", () => {
  it("reads the REE's steps as shipped", () => {
    const progress = mapRawAuthoringProgress({
      steps: [
        { key: "source", order: 1, label: "Source Acquisition", requires: [], status: "complete" },
        { key: "evaluate", order: 4, label: "Readiness", requires: ["source"], status: "ready" },
      ],
      next: "evaluate",
    });

    expect(progress.next).toBe("evaluate");
    expect(progress.steps.map((step) => step.status)).toEqual(["complete", "ready"]);
    expect(isAuthoringStepComplete(progress, "source")).toBe(true);
    expect(isAuthoringStepComplete(progress, "evaluate")).toBe(false);
  });

  it("drops what it does not know and claims nothing done", () => {
    const progress = mapRawAuthoringProgress({
      steps: [
        { key: "unknown", order: 1, label: "?", status: "complete" },
        { key: "seal", order: 10, label: "Seal", status: "finished" },
      ],
      next: "unknown",
    });

    expect(progress.steps.map((step) => [step.key, step.status])).toEqual([["seal", "blocked"]]);
    expect(progress.next).toBeUndefined();
    expect(mapRawAuthoringProgress(undefined)).toEqual({ steps: [], next: undefined });
  });
});
