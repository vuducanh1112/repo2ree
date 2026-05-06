import { describe, expect, it } from "vitest";
import type { InclusionStatus, ReeInclusionState } from "./ReeInclusionState";
import { deriveReeInclusionState, mapLegacyInclusionState } from "./ReeInclusionState";
import { createEmptyReeSpec } from "./ReeSpec";

describe("mapLegacyInclusionState", () => {
  it("marks source unavailable when source is not available", () => {
    const state = mapLegacyInclusionState({
      sourceAvailable: false,
      sourceIncluded: false,
      runtimeIncluded: false,
    });

    expect(state.source).toBe("unavailable");
    expect(state.runtime).toBe("unavailable");
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

describe("deriveReeInclusionState", () => {
  it("marks all optional assets unavailable for metadata-only REE", () => {
    const state = deriveReeInclusionState({
      reeSpec: createEmptyReeSpec(),
      workspaceSourceState: {
        sourceAvailable: false,
        sourceIncluded: false,
      },
      artifactStatus: {
        runtimeIncluded: false,
        downloadableFiles: [],
      },
    });

    expect(state).toEqual({
      source: "unavailable",
      runtime: "unavailable",
    });
  });

  it("supports source available but excluded", () => {
    const state = deriveReeInclusionState({
      reeSpec: createEmptyReeSpec(),
      workspaceSourceState: {
        sourceAvailable: true,
        sourceIncluded: false,
      },
      artifactStatus: {
        downloadableFiles: [],
      },
    });
    expect(state.source).toBe("excluded");
  });

  it("supports source included", () => {
    const state = deriveReeInclusionState({
      reeSpec: createEmptyReeSpec(),
      workspaceSourceState: {
        sourceAvailable: true,
        sourceIncluded: true,
      },
      artifactStatus: {
        downloadableFiles: [],
      },
    });
    expect(state.source).toBe("included");
  });

  it("supports runtime generated but excluded", () => {
    const state = deriveReeInclusionState({
      reeSpec: {
        ...createEmptyReeSpec(),
        runtime: "runtime.tar.gz",
      },
      workspaceSourceState: {
        sourceAvailable: true,
      },
      artifactStatus: {
        runtimeIncluded: false,
        downloadableFiles: [],
      },
    });
    expect(state.runtime).toBe("excluded");
  });

  it("supports runtime included", () => {
    const state = deriveReeInclusionState({
      reeSpec: {
        ...createEmptyReeSpec(),
        runtime: "runtime.tar.gz",
      },
      workspaceSourceState: {
        sourceAvailable: true,
      },
      artifactStatus: {
        runtimeIncluded: true,
        downloadableFiles: ["runtime.tar.gz"],
      },
    });
    expect(state.runtime).toBe("included");
  });

  it("keeps runtime unavailable when runtimeIncluded is true but runtime is blank", () => {
    const state = deriveReeInclusionState({
      reeSpec: createEmptyReeSpec(),
      workspaceSourceState: {
        sourceAvailable: true,
      },
      artifactStatus: {
        runtimeIncluded: true,
      },
    });
    expect(state.runtime).toBe("unavailable");
  });
});
