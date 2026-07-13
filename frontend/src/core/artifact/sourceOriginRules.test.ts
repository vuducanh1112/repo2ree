import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import { enforceSourceOriginRules } from "./sourceOriginRules";

describe("enforceSourceOriginRules", () => {
  it("clears originUrl when the source was not acquired by download", () => {
    const result = enforceSourceOriginRules({
      reeSpec: {
        ...createEmptyReeSpec(),
        originUrl: "https://example.org/repo.git",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceAcquiredBy: "upload",
        sourceIncluded: true,
      },
      artifactStatus: { runtimeIncluded: false },
      evaluationState: { dependencyLevel: 0 },
    });

    expect(result.reeSpec.originUrl).toBe("");
  });

  it("preserves identities when no updates are needed", () => {
    const reeSpec = {
      ...createEmptyReeSpec(),
      originUrl: "https://example.org/repo.git",
    };
    const workspaceSourceState = {
      sourceAvailable: true,
      sourceAcquiredBy: "download" as const,
      sourceIncluded: true,
    };

    const state = {
      reeSpec,
      workspaceSourceState,
      artifactStatus: { runtimeIncluded: true },
      evaluationState: { dependencyLevel: 2 },
    };
    const result = enforceSourceOriginRules(state);

    expect(result.reeSpec).toBe(reeSpec);
    expect(result.workspaceSourceState).toBe(workspaceSourceState);
    expect(result).toBe(state);
  });
});
