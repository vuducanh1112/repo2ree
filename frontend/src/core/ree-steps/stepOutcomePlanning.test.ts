import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  planActivationEffect,
  planBuildEffect,
  planEvaluateEffect,
  planHbomEffect,
  planSbomEffect,
  planStepServiceEffect,
} from "./stepOutcomePlanning";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("stepOutcomePlanning", () => {
  it("produces a success message naming the runtime when one is set", () => {
    const result = planBuildEffect({ ree: { ...buildRee(), runtime: "runtime.tar.gz" } });
    expect(result.successMessage).toContain("runtime.tar.gz");
  });

  it("plans HBOM success messaging", () => {
    const result = planHbomEffect();
    expect(result.successMessage).toContain("current machine");
  });

  it("declares the SBOM at the REE's own artifact path, not a workspace file", () => {
    const result = planSbomEffect();

    expect(result.reeSpecPatch.sbom).toBe("artifacts/sbom.json");
  });

  it("plans evaluate metadata", () => {
    const result = planEvaluateEffect();

    expect(result.evaluationStatePatch).toEqual({});
    expect(result.successMessage).toBe("Evaluate complete");
  });

  it("plans activation success text", () => {
    expect(planActivationEffect().successMessage).toContain("Activation test passed");
  });

  it("builds step effect plans through a single entry point", () => {
    const result = planStepServiceEffect({
      key: "build",
      params: {},
      ree: buildRee(),
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
    });

    expect(result.successMessage).toContain("Build complete");
  });

  it("builds evaluate step effect plans through a single entry point", () => {
    const result = planStepServiceEffect({
      key: "evaluate",
      params: {},
      ree: buildRee(),
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
    });

    expect(result.successMessage).toBe("Evaluate complete");
  });
});
