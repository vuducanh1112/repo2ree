import { UnknownWireNames } from "@core/contract/unknownNames";
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

  it("claims nothing done on a status it does not know", () => {
    const progress = mapRawAuthoringProgress({
      steps: [{ key: "seal_ree", order: 10, label: "Seal", status: "finished" }],
    });

    expect(progress.steps.map((step) => [step.key, step.status])).toEqual([
      ["seal_ree", "blocked"],
    ]);
    expect(progress.next).toBeUndefined();
    expect(mapRawAuthoringProgress(undefined)).toEqual({ steps: [], next: undefined });
  });

  it("refuses a step the contract does not name, wherever it appears", () => {
    const step = { order: 1, label: "?", status: "complete" };
    expect(() => mapRawAuthoringProgress({ steps: [{ ...step, key: "source" }] })).toThrow(
      UnknownWireNames,
    );
    expect(() =>
      mapRawAuthoringProgress({
        steps: [{ ...step, key: "seal_ree", requires: ["sealing"] }],
      }),
    ).toThrow(/sealing/);
    expect(() => mapRawAuthoringProgress({ steps: [], next: "source" })).toThrow(UnknownWireNames);
  });

  it("reads the working environment check without showing it", () => {
    const progress = mapRawAuthoringProgress({
      steps: [
        { key: "check_working_environment", order: 4, label: "Check", status: "complete" },
        {
          key: "evaluate_reproducibility",
          order: 5,
          label: "Readiness",
          requires: ["check_working_environment"],
          status: "ready",
        },
      ],
    });

    expect(progress.steps.map((step) => [step.key, step.requires])).toEqual([
      ["evaluate_reproducibility", []],
    ]);
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
