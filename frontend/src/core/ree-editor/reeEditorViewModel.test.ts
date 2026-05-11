import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../../core/ree/ReeSpec";
import { createReeEditorState } from "./reeEditorState";
import { createEmptyReeEditorViewModel, createReeEditorViewModel } from "./reeEditorViewModel";

describe("reeEditorViewModel", () => {
  it("assembles the UI view model from explicit editor slices", () => {
    const editorState = createReeEditorState({
      reeSpec: {
        ...createEmptyReeSpec(),
        name: "demo",
        origin_url: "https://example.org/repo.git",
        source_type: "git",
        runtime: "runtime.tar.gz",
        build_runtime_script: "build_runtime.sh",
        activation_script: "activation_test.sh",
        sbom: "sbom.spdx.json",
        swhid: "swh:1:dir:abc",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceIncluded: true,
        sourceAcquiredBy: "download",
      },
      artifactStatus: {
        runtimeIncluded: true,
        downloadableFiles: ["runtime.tar.gz"],
        sealedAt: "2026-01-01T00:00:00Z",
      },
      evaluationState: {
        evalLevel: 3,
      },
    });

    const viewModel = createReeEditorViewModel(editorState);

    expect(viewModel.name).toBe("demo");
    expect(viewModel.sourceAvailable).toBe(true);
    expect(viewModel.runtimeIncluded).toBe(true);
    expect(viewModel.evalLevel).toBe(3);
  });

  it("creates an empty view model with product and editor defaults", () => {
    const viewModel = createEmptyReeEditorViewModel();

    expect(viewModel.name).toBe("");
    expect(viewModel.sourceAvailable).toBe(false);
    expect(viewModel.runtimeIncluded).toBe(false);
    expect(viewModel.evalLevel).toBe(0);
  });

  it("derives inclusion state from source and artifact booleans", () => {
    const editorState = createReeEditorState({
      reeSpec: {
        ...createEmptyReeSpec(),
        runtime: "runtime.tar.gz",
      },
      workspaceSourceState: {
        sourceAvailable: true,
        sourceIncluded: false,
      },
      artifactStatus: {
        runtimeIncluded: true,
        downloadableFiles: [],
      },
    });

    expect(editorState.inclusionState).toEqual({
      source: "excluded",
      runtime: "included",
    });
  });
});
