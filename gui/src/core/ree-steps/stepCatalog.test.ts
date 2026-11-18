import { describe, expect, it } from "vitest";
import { initialReeStepParams, mergeStepParams } from "./stepCatalog";

describe("mergeStepParams", () => {
  it("merges automation step params into the existing step param map", () => {
    expect(
      mergeStepParams(initialReeStepParams(), "evaluate_reproducibility", {
        strict: true,
      }),
    ).toEqual({
      evaluate_reproducibility: { strict: true },
      build_experiment_environment: {},
      observe_hardware: {},
      generate_sbom: {},
      activate_experiment_environment: {},
    });
  });

  it("leaves other steps untouched", () => {
    const merged = mergeStepParams(initialReeStepParams(), "evaluate_reproducibility", {
      strict: true,
    });
    expect(merged.generate_sbom).toEqual({});
    expect(merged.evaluate_reproducibility).toEqual({ strict: true });
  });
});
