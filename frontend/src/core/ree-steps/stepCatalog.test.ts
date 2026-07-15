import { describe, expect, it } from "vitest";
import { initialReeStepParams, mergeStepParams } from "./stepCatalog";

describe("mergeStepParams", () => {
  it("merges automation step params into the existing step param map", () => {
    expect(
      mergeStepParams(initialReeStepParams(), "evaluate", {
        strict: true,
      }),
    ).toEqual({
      evaluate: { strict: true },
      build: {},
      hbom: {},
      sbom: {},
      activation: {},
    });
  });

  it("leaves other steps untouched", () => {
    const merged = mergeStepParams(initialReeStepParams(), "evaluate", { strict: true });
    expect(merged.sbom).toEqual({});
    expect(merged.evaluate).toEqual({ strict: true });
  });
});
