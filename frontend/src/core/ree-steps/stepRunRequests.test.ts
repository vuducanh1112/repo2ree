import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  buildActivationStepRunRequest,
  buildBuildStepRunRequest,
  buildEvaluateStepRunRequest,
  buildSbomStepRunRequest,
} from "./stepRunRequests";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
    runtime: "runtime.tar.gz",
  };
}

describe("stepRunRequests", () => {
  it("builds explicit evaluate request payloads", () => {
    expect(buildEvaluateStepRunRequest({ strict: true })).toEqual({
      scriptKey: "evaluate",
      params: {
        strict: true,
      },
    });
  });

  it("builds a parameterless build request (reserved script is fixed)", () => {
    expect(buildBuildStepRunRequest({}, buildRee())).toEqual({
      scriptKey: "build",
      params: {},
    });
  });

  it("maps sbom and activation inputs into backend request fields", () => {
    const ree = buildRee();

    expect(buildSbomStepRunRequest({}, ree)).toEqual({
      scriptKey: "sbom",
      params: {
        produced_runtime_path: "runtime.tar.gz",
      },
    });
    expect(buildActivationStepRunRequest({}, ree)).toEqual({
      scriptKey: "activation",
      params: {},
    });
  });
});
