import { describe, expect, it } from "vitest";
import { isAuthoringStepComplete, mapRawAuthoringProgress } from "./AuthoringProgress";

describe("authoring progress", () => {
  it("reads the REE's steps as shipped", () => {
    const progress = mapRawAuthoringProgress({
      steps: [
        {
          key: "acquire_source",
          order: 1,
          label: "Source Acquisition",
          requires: [],
          status: "complete",
        },
        {
          key: "evaluate_reproducibility",
          order: 4,
          label: "Readiness",
          requires: ["acquire_source"],
          status: "ready",
        },
      ],
      next: "evaluate_reproducibility",
    });

    expect(progress.next).toBe("evaluate_reproducibility");
    expect(progress.steps.map((step) => step.status)).toEqual(["complete", "ready"]);
    expect(isAuthoringStepComplete(progress, "acquire_source")).toBe(true);
    expect(isAuthoringStepComplete(progress, "evaluate_reproducibility")).toBe(false);
  });

  it("drops what it does not know and claims nothing done", () => {
    const progress = mapRawAuthoringProgress({
      steps: [
        { key: "unknown", order: 1, label: "?", status: "complete" },
        { key: "seal_ree", order: 10, label: "Seal", status: "finished" },
      ],
      next: "unknown",
    });

    expect(progress.steps.map((step) => [step.key, step.status])).toEqual([
      ["seal_ree", "blocked"],
    ]);
    expect(progress.next).toBeUndefined();
    expect(mapRawAuthoringProgress(undefined)).toEqual({ steps: [], next: undefined });
  });

  it("offers the first ready step it can show when the next one is a step it has no page for", () => {
    const progress = mapRawAuthoringProgress({
      steps: [
        {
          key: "check_working_environment",
          order: 4,
          label: "Check",
          requires: [],
          status: "ready",
        },
        {
          key: "evaluate_reproducibility",
          order: 5,
          label: "Readiness",
          requires: [],
          status: "ready",
        },
        { key: "seal_ree", order: 11, label: "Seal", requires: [], status: "ready" },
      ],
      next: "check_working_environment",
    });

    expect(progress.next).toBe("evaluate_reproducibility");
  });
});
