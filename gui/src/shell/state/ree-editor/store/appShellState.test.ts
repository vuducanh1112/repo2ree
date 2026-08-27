import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
  type ReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { describe, expect, it } from "vitest";
import { clearToast, resetStepsAfterSourceChange, showToast, updateReeSpec } from "./actions";
import { appShellReducer, createInitialState } from "./appShellReducer";
import { createAppShellState } from "./appShellState";

function buildRee(): ReeEditorViewModel {
  return patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
    spec: { name: "demo" },
  });
}

function toInitialSlices(ree: ReeEditorViewModel) {
  return {
    reeSpec: ree.spec,
    workspaceSourceState: ree.source,
    artifactStatus: ree.artifact,
    evaluationState: ree.evaluation,
  };
}

describe("appShellState", () => {
  it("applies source patch outcomes to ree and source status metadata", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));

    const next = appShellReducer(initial, {
      type: "applySourceOutcome",
      outcome: {
        reeSpecPatch: {
          originUrl: "https://example.org/repo.git",
        },
        workspaceSourceStatePatch: {
          sourceAvailable: true,
          sourceAcquiredBy: "download",
        },
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });
    expect(next.reeIntent.reeSpec.originUrl).toBe("https://example.org/repo.git");
  });

  it("resets step-dependent workspace state on source change", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));

    const next = appShellReducer(initial, resetStepsAfterSourceChange(initial.stepRuns.stepParams));

    expect(next.reeIntent.reeSpec.originUrl).toBe("");
  });

  it("keeps the aggregate selector aligned with the slice state", () => {
    const state = createInitialState(toInitialSlices(buildRee()));

    const view = createAppShellState(state);

    expect(view.page).toBe(state.uiChrome.page);
    expect(view.stepParams).toBe(state.stepRuns.stepParams);
    expect(createEmptyReeEditorViewModel().spec.name).toBe("");
  });

  it("updates the local definition draft", () => {
    const initial = createInitialState(
      toInitialSlices(
        patchReeEditorViewModel(buildRee(), {
          source: { sourceAvailable: true, sourceIncluded: true },
          artifact: { runtimeIncluded: true },
        }),
      ),
    );

    const next = appShellReducer(
      initial,
      updateReeSpec((prev) => ({
        ...prev,
        name: "renamed",
      })),
    );

    expect(next.reeIntent.reeSpec.name).toBe("renamed");
  });

  it("shows and clears toast via named transitions", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const shown = appShellReducer(initial, showToast({ message: "Saved", type: "success" }));
    expect(shown.uiChrome.toast).toEqual({ message: "Saved", type: "success" });
    const cleared = appShellReducer(shown, clearToast());
    expect(cleared.uiChrome.toast).toBeNull();
  });
});
