import { describe, expect, it } from "vitest";
import type { InclusionStatus, ReeInclusionState } from "./ReeInclusionState";
import { mapLegacyInclusionState } from "./ReeInclusionState";

describe("mapLegacyInclusionState", () => {
  it("marks source unavailable when source is not available", () => {
    const state = mapLegacyInclusionState({
      sourceAvailable: false,
      sourceIncluded: false,
      runtimeIncluded: false,
    });

    expect(state.source).toBe("unavailable");
    expect(state.runtime).toBe("unavailable");
    expect(state.sbom).toBe("unavailable");
    expect(state.hbom).toBe("unavailable");
    expect(state.activationEvidence).toBe("unavailable");
  });

  it("maps available and included source/runtime values", () => {
    const included = mapLegacyInclusionState({
      sourceAvailable: true,
      sourceIncluded: true,
      runtimeIncluded: true,
    });
    const excluded = mapLegacyInclusionState({
      sourceAvailable: true,
      sourceIncluded: false,
      runtimeIncluded: false,
    });

    expect(included.source).toBe("included");
    expect(included.runtime).toBe("included");
    expect(excluded.source).toBe("excluded");
    expect(excluded.runtime).toBe("excluded");
  });

  it("produces canonical inclusion vocabulary values", () => {
    const state: ReeInclusionState = mapLegacyInclusionState({
      sourceAvailable: true,
      sourceIncluded: true,
      runtimeIncluded: false,
    });
    const statuses: InclusionStatus[] = [state.source, state.runtime];
    expect(statuses).toEqual(["included", "excluded"]);
  });
});
