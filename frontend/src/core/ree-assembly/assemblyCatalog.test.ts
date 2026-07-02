import { describe, expect, it } from "vitest";
import { initialReeAssemblyOperationParams, mergeAssemblyOperationParams } from "./assemblyCatalog";

describe("mergeAssemblyOperationParams", () => {
  it("merges automation step params into the existing assembly param map", () => {
    expect(
      mergeAssemblyOperationParams(initialReeAssemblyOperationParams(), "activation", {
        mode: "snapshot",
      }),
    ).toEqual({
      evaluate: { strict: false },
      build: {},
      hbom: {},
      sbom: { format: "spdx-json" },
      activation: { mode: "snapshot" },
    });
  });

  it("leaves other steps untouched", () => {
    const merged = mergeAssemblyOperationParams(initialReeAssemblyOperationParams(), "sbom", {
      format: "cyclonedx-json",
    });
    expect(merged.sbom).toEqual({ format: "cyclonedx-json" });
    expect(merged.evaluate).toEqual({ strict: false });
  });
});
