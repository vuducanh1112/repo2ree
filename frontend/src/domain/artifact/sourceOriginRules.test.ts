import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import { enforceSourceOriginRulesForSlices } from "./sourceOriginRules";

describe("enforceSourceOriginRulesForSlices", () => {
  it("clears origin_url when the source was not acquired by download", () => {
    const result = enforceSourceOriginRulesForSlices({
      reeSpec: {
        ...createEmptyReeSpec(),
        origin_url: "https://example.org/repo.git",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceAcquiredBy: "upload",
        sourceIncluded: true,
      },
    });

    expect(result.reeSpec.origin_url).toBe("");
  });

  it("forces uploaded sources to remain included", () => {
    const result = enforceSourceOriginRulesForSlices({
      reeSpec: {
        ...createEmptyReeSpec(),
        origin_url: "https://example.org/repo.git",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceAcquiredBy: "upload",
        sourceIncluded: false,
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

    const result = enforceSourceOriginRulesForSlices({ reeSpec, workspaceSourceState });

    expect(result.reeSpec).toBe(reeSpec);
    expect(result.workspaceSourceState).toBe(workspaceSourceState);
  });
});
