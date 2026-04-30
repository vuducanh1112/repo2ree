import { describe, expect, it } from "vitest";
import type { Ree } from "../../domain/ree/ReeSpec";
import {
  planActivationEffect,
  planBuildEffect,
  planEvaluateEffect,
  planHbomEffect,
  planSbomEffect,
  planWorkflowServiceEffect,
} from "./workflowOutcomePlanning";

function buildRee(): Ree {
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

describe("workflowOutcomePlanning", () => {
  it("plans mock build artifact persistence", () => {
    const result = planBuildEffect({
      ree: buildRee(),
      expectedOutput: "runtime.tar.gz",
      workspaceServiceMode: "mock",
      timestamp: "2026-01-01T00:00:00Z",
    });

    expect(result.persistedFile?.path).toBe("runtime.tar.gz");
    expect(result.reePatch?.runtime).toBe("runtime.tar.gz");
  });

  it("plans mock HBOM population", () => {
    const result = planHbomEffect("mock");

    expect(result.reePatch?.hardware_description?.cpus).toBeDefined();
    expect(result.successMessage).toContain("mock machine");
  });

  it("plans mock SBOM persistence", () => {
    const result = planSbomEffect({
      ree: buildRee(),
      workspaceServiceMode: "mock",
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
    });

    expect(result.persistedFile?.path).toBe("sbom.json");
    expect(result.reePatch.sbom).toBe("sbom.json");
  });

  it("plans evaluate metadata", () => {
    const result = planEvaluateEffect({
      newLevel: 3,
      dependencyCount: 5,
      manifestCount: 2,
    });

    expect(result.reePatch._evalLevel).toBe(3);
    expect(result.reePatch.detected_dependencies).toContain("5 dependencies");
    expect(result.successMessage).toContain("L3");
  });

  it("plans activation success text", () => {
    expect(planActivationEffect().successMessage).toContain("Activation test passed");
  });

  it("builds workflow effect plans through a single entry point", () => {
    const result = planWorkflowServiceEffect({
      key: "build",
      params: { _expectedOutput: "runtime.tar.gz" },
      ree: buildRee(),
      newLevel: 2,
      workspaceServiceMode: "mock",
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
      dependencyCount: 0,
      manifestCount: 0,
    });

    expect(result.persistedFile?.path).toBe("runtime.tar.gz");
    expect(result.reePatch?.runtime).toBe("runtime.tar.gz");
  });

  it("builds evaluate workflow effect plans through a single entry point", () => {
    const result = planWorkflowServiceEffect({
      key: "evaluate",
      params: {},
      ree: buildRee(),
      newLevel: 4,
      workspaceServiceMode: "mock",
      timestamp: "2026-01-01T00:00:00Z",
      namespaceSuffix: "123",
      dependencyCount: 7,
      manifestCount: 3,
    });

    expect(result.reePatch?._evalLevel).toBe(4);
    expect(result.successMessage).toContain("L4");
  });
});
