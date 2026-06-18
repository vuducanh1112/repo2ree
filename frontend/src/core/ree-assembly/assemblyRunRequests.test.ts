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
    build_runtime_script: "scripts/build.sh",
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

  it("maps build inputs into backend request fields", () => {
    expect(buildBuildAssemblyRunRequest({}, buildRee())).toEqual({
      scriptKey: "build",
      params: {
        build_runtime_script_path: "scripts/build.sh",
      },
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
    expect(buildActivationAssemblyRunRequest({ mode: "verify" }, ree)).toEqual({
      scriptKey: "activation",
      params: {
        mode: "verify",
      },
    });
  });
});
