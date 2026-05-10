import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  planActivationEffect,
  planAssemblyServiceEffect,
  planBuildEffect,
  planEvaluateEffect,
  planHbomEffect,
  planSbomEffect,
} from "./assemblyOutcomePlanning";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
  };
}

describe("assemblyOutcomePlanning", () => {
  it("produces a success message naming the runtime when one is set", () => {
    const result = planBuildEffect({ ree: buildRee() });
    expect(result.successMessage).toContain("runtime.tar.gz");
  });

  it("plans HBOM success messaging", () => {
    const result = planHbomEffect();
    expect(result.successMessage).toContain("current machine");
  });

  it("plans SBOM metadata", () => {
    const result = planSbomEffect();

    expect(result.reeSpecPatch.sbom).toBe("sbom.json");
  });

  it("plans evaluate metadata", () => {
    const result = planEvaluateEffect({
      newLevel: 3,
      dependencyCount: 5,
      manifestCount: 2,
    });

    expect(result.evaluationStatePatch.evalLevel).toBe(3);
    expect(result.reeSpecPatch.detected_dependencies).toContain("5 dependencies");
    expect(result.successMessage).toContain("L3");
  });

  it("plans activation success text", () => {
    expect(planActivationEffect().successMessage).toContain("Activation test passed");
  });

  it("builds assembly effect plans through a single entry point", () => {
    const result = planAssemblyServiceEffect({
      key: "build",
      params: {},
      ree: buildRee(),
      newLevel: 2,
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
      dependencyCount: 0,
      manifestCount: 0,
    });

    expect(result.successMessage).toContain("Build complete");
  });

  it("builds evaluate assembly effect plans through a single entry point", () => {
    const result = planAssemblyServiceEffect({
      key: "evaluate",
      params: {},
      ree: buildRee(),
      newLevel: 4,
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
      dependencyCount: 7,
      manifestCount: 3,
    });

    expect(result.evaluationStatePatch?.evalLevel).toBe(4);
    expect(result.successMessage).toContain("L4");
  });
});
