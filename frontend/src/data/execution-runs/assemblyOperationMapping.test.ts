import { describe, expect, it } from "vitest";
import type { ReeAssemblyOperation } from "../../application/ree-assembly/assemblyOperation";
import {
  fromBackendWorkflowOperation,
  toBackendWorkflowOperation,
} from "./assemblyOperationMapping";

describe("assembly operation mapping", () => {
  it("maps ree assembly operations to backend workflow operations", () => {
    const operations: ReeAssemblyOperation[] = [
      "generateHbom",
      "buildRuntime",
      "generateSbom",
      "testActivation",
    ];
    expect(toBackendWorkflowOperation(operations[0])).toBe("hbom");
    expect(toBackendWorkflowOperation(operations[1])).toBe("build");
    expect(toBackendWorkflowOperation(operations[2])).toBe("sbom");
    expect(toBackendWorkflowOperation(operations[3])).toBe("activation");
  });

  it("maps backend workflow operations to ree assembly operations", () => {
    expect(fromBackendWorkflowOperation("hbom")).toBe("generateHbom");
    expect(fromBackendWorkflowOperation("build")).toBe("buildRuntime");
    expect(fromBackendWorkflowOperation("sbom")).toBe("generateSbom");
    expect(fromBackendWorkflowOperation("activation")).toBe("testActivation");
  });

  it("returns null for non-assembly backend operations", () => {
    expect(fromBackendWorkflowOperation("evaluate")).toBeNull();
    expect(fromBackendWorkflowOperation("source")).toBeNull();
    expect(fromBackendWorkflowOperation("swh")).toBeNull();
    expect(fromBackendWorkflowOperation("zenodo")).toBeNull();
    expect(fromBackendWorkflowOperation("dataverse")).toBeNull();
  });
});
