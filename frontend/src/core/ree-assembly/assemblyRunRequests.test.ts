import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildActivationAssemblyRunRequest,
  buildBuildAssemblyRunRequest,
  buildEvaluateAssemblyRunRequest,
  buildSbomAssemblyRunRequest,
} from "./assemblyRunRequests";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
    runtime: "runtime.tar.gz",
  };
}

describe("assemblyRunRequests", () => {
  it("builds explicit evaluate request payloads", () => {
    expect(buildEvaluateAssemblyRunRequest({ strict: true })).toEqual({
      scriptKey: "evaluate",
      params: {
        strict: true,
      },
    });
  });

  it("builds a parameterless build request (reserved script is fixed)", () => {
    expect(buildBuildAssemblyRunRequest({}, buildRee())).toEqual({
      scriptKey: "build",
      params: {},
    });
  });

  it("maps sbom and activation inputs into backend request fields", () => {
    const ree = buildRee();

    expect(buildSbomAssemblyRunRequest({ format: "spdx-json" }, ree)).toEqual({
      scriptKey: "sbom",
      params: {
        produced_runtime_path: "runtime.tar.gz",
      },
    });
    expect(buildActivationAssemblyRunRequest({}, ree)).toEqual({
      scriptKey: "activation",
      params: {},
    });
  });
});
