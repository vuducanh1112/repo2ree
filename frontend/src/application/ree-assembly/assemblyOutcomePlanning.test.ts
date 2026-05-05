import { describe, expect, it } from "vitest";
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
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
    sbom: "",
    swhid: "",
    hardware_description: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extra_info: {},
    },
  };
}

describe("assemblyOutcomePlanning", () => {
  it("records the expected runtime path when build output is declared", () => {
    const result = planBuildEffect({
      ree: buildRee(),
      expectedOutput: "runtime.tar.gz",
    });

    expect(result.reePatch?.runtime).toBe("runtime.tar.gz");
  });

  it("plans HBOM success messaging", () => {
    const result = planHbomEffect();
    expect(result.successMessage).toContain("current machine");
  });

  it("plans SBOM metadata", () => {
    const result = planSbomEffect();

    expect(result.reePatch.sbom).toBe("sbom.json");
  });

  it("plans evaluate metadata", () => {
    const result = planEvaluateEffect({
      newLevel: 3,
      dependencyCount: 5,
      manifestCount: 2,
    });

    expect(result.reePatch.evalLevel).toBe(3);
    expect(result.reePatch.detected_dependencies).toContain("5 dependencies");
    expect(result.successMessage).toContain("L3");
  });

  it("plans activation success text", () => {
    expect(planActivationEffect().successMessage).toContain("Activation test passed");
  });

  it("builds assembly effect plans through a single entry point", () => {
    const result = planAssemblyServiceEffect({
      key: "build",
      params: { _expectedOutput: "runtime.tar.gz" },
      ree: buildRee(),
      newLevel: 2,
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
      dependencyCount: 0,
      manifestCount: 0,
    });

    expect(result.reePatch?.runtime).toBe("runtime.tar.gz");
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

    expect(result.reePatch?.evalLevel).toBe(4);
    expect(result.successMessage).toContain("L4");
  });
});
