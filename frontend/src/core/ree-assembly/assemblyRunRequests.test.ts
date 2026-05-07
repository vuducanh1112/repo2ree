import { describe, expect, it } from "vitest";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildActivationAssemblyRunRequest,
  buildBuildAssemblyRunRequest,
  buildEvaluateAssemblyRunRequest,
  buildSbomAssemblyRunRequest,
} from "./assemblyRunRequests";

function buildRee(): ReeEditorViewModel {
  return {
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "runtime.tar.gz",
    build_runtime_script: "scripts/build.sh",
    activation_script: "scripts/activate.sh",
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

describe("assemblyRunRequests", () => {
  it("builds explicit evaluate request payloads", () => {
    expect(buildEvaluateAssemblyRunRequest({ strict: true, swhid_check: false })).toEqual({
      scriptKey: "evaluate",
      params: {
        strict: true,
        swhid_check: false,
      },
    });
  });

  it("maps build inputs into backend request fields", () => {
    expect(
      buildBuildAssemblyRunRequest({ no_cache: true, platform: "linux/amd64" }, buildRee()),
    ).toEqual({
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
    expect(buildActivationAssemblyRunRequest({ timeout: "60", verbose: false }, ree)).toEqual({
      scriptKey: "activation",
      params: {
        activation_script_path: "scripts/activate.sh",
      },
    });
  });
});
