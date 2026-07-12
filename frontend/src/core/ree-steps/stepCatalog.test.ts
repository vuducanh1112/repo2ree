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
      sbom: { format: "spdx-json" },
      activation: {},
    });
  });

  it("leaves other steps untouched", () => {
    const merged = mergeStepParams(initialReeStepParams(), "sbom", {
      format: "cyclonedx-json",
    });
    expect(merged.sbom).toEqual({ format: "cyclonedx-json" });
    expect(merged.evaluate).toEqual({ strict: false });
  });
});
