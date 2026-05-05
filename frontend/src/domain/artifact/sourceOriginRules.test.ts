import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import { enforceSourceOriginRules } from "./sourceOriginRules";

describe("enforceSourceOriginRules", () => {
  it("clears origin_url when the source was not acquired by download", () => {
    const result = enforceSourceOriginRules({
      reeSpec: {
        ...createEmptyReeSpec(),
        origin_url: "https://example.org/repo.git",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceAcquiredBy: "upload",
        sourceIncluded: true,
      },
      artifactStatus: {
        runtimeIncluded: false,
        downloadableFiles: [],
      },
      evaluationState: {
        evalLevel: 0,
      },
    });

    expect(result.reeSpec.origin_url).toBe("");
  });

  it("forces uploaded sources to remain included", () => {
    const result = enforceSourceOriginRules({
      reeSpec: {
        ...createEmptyReeSpec(),
        origin_url: "https://example.org/repo.git",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceAcquiredBy: "upload",
        sourceIncluded: false,
      },
      artifactStatus: {
        runtimeIncluded: false,
        downloadableFiles: [],
      },
      evaluationState: {
        evalLevel: 0,
      },
    });

    expect(result.workspaceSourceState.sourceIncluded).toBe(true);
  });

  it("preserves identities when no updates are needed", () => {
    const reeSpec = {
      ...createEmptyReeSpec(),
      origin_url: "https://example.org/repo.git",
    };
    const workspaceSourceState = {
      sourceAvailable: true,
      sourceAcquiredBy: "download" as const,
      sourceIncluded: true,
    };

    const state = {
      reeSpec,
      workspaceSourceState,
      artifactStatus: {
        runtimeIncluded: true,
        downloadableFiles: [],
      },
      evaluationState: {
        evalLevel: 2,
      },
    };
    const result = enforceSourceOriginRules(state);

    expect(result.reeSpec).toBe(reeSpec);
    expect(result.workspaceSourceState).toBe(workspaceSourceState);
    expect(result).toBe(state);
  });
});
