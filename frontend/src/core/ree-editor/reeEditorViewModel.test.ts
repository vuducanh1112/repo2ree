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
        originUrl: "https://example.org/repo.git",
        sourceType: "git",
        runtime: "runtime.tar.gz",
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
        sealedAt: "2026-01-01T00:00:00Z",
      },
      evaluationState: {
        dependencyLevel: 3,
      },
    });

    const viewModel = createReeEditorViewModel(editorState);

    expect(viewModel.name).toBe("demo");
    expect(viewModel.sourceAvailable).toBe(true);
    expect(viewModel.runtimeIncluded).toBe(true);
    expect(viewModel.dependencyLevel).toBe(3);
  });

  it("creates an empty view model with product and editor defaults", () => {
    const viewModel = createEmptyReeEditorViewModel();

    expect(viewModel.name).toBe("");
    expect(viewModel.sourceAvailable).toBe(false);
    expect(viewModel.runtimeIncluded).toBe(false);
    expect(viewModel.dependencyLevel).toBe(0);
  });
});
