import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
  type ReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { describe, expect, it } from "vitest";
import {
  cancelStepRun,
  clearToast,
  completeStepRun,
  resetStepsAfterSourceChange,
  setActiveRunId,
  setArtifactStatus,
  setEvaluationState,
  setStepRunLoading,
  setWorkspaceSourceState,
  showToast,
  updateReeSpec,
} from "./actions";
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
        sourceSnapshotArchiveName: "repo-original.tar.gz",
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });
    const view = createAppShellState(next);

    expect(next.reeIntent.reeSpec.originUrl).toBe("https://example.org/repo.git");
    expect(next.reeSession.workspaceSourceState.sourceAvailable).toBe(true);
    expect(next.stepRuns.actionStates.source).toBe("done");
    expect(next.stepRuns.badges.source).toBe(true);
    expect(next.stepRuns.timestamps.source).toBe("2026-01-01T00:00:00Z");
    expect(next.uiChrome.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
    expect(view.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
  });

  it("records completion metadata for completed step runs", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));

    const next = appShellReducer(
      initial,
      completeStepRun({
        key: "build",
        actionState: "done",
        badge: "succeeded",
        timestamp: "2026-01-01T00:00:00Z",
      }),
    );

    expect(next.stepRuns.actionStates.build).toBe("done");
    expect(next.stepRuns.badges.build).toBe("succeeded");
    expect(next.stepRuns.timestamps.build).toBe("2026-01-01T00:00:00Z");
  });

  it("resets step-dependent workspace state on source change", () => {
    const initial = {
      ...createInitialState(toInitialSlices(buildRee())),
      stepRuns: {
        ...createInitialState(toInitialSlices(buildRee())).stepRuns,
        actionStates: { build: "done" as const },
        badges: { build: true },
        timestamps: { build: "2026-01-01T00:00:00Z" },
      },
    };

    const next = appShellReducer(initial, resetStepsAfterSourceChange(initial.stepRuns.stepParams));

    expect(next.stepRuns.actionStates).toEqual({});
    expect(next.stepRuns.badges).toEqual({});
    expect(next.stepRuns.timestamps).toEqual({});
    expect(next.reeIntent.reeSpec.originUrl).toBe("");
    expect(next.reeSession.workspaceSourceState.sourceAvailable).toBe(false);
  });

  it("keeps the aggregate selector aligned with the slice state", () => {
    const state = createInitialState(toInitialSlices(buildRee()));

    const view = createAppShellState(state);

    expect(view.page).toBe(state.uiChrome.page);
    expect(view.stepParams).toBe(state.stepRuns.stepParams);
    expect(view.locked).toBe(state.uiChrome.locked);
    expect(createEmptyReeEditorViewModel().spec.name).toBe("");
  });

  it("updates ree metadata without mutating source or artifact slices", () => {
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
    expect(next.reeSession.workspaceSourceState).toEqual(initial.reeSession.workspaceSourceState);
    expect(next.reeSession.artifactStatus).toEqual(initial.reeSession.artifactStatus);
  });

  it("updates workspace source state via named transition", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const next = appShellReducer(
      initial,
      setWorkspaceSourceState((prev) => ({ ...prev, sourceAvailable: true })),
    );
    expect(next.reeSession.workspaceSourceState.sourceAvailable).toBe(true);
  });

  it("updates artifact status via named transition", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const next = appShellReducer(
      initial,
      setArtifactStatus((prev) => ({ ...prev, runtimeIncluded: true })),
    );
    expect(next.reeSession.artifactStatus.runtimeIncluded).toBe(true);
  });

  it("updates evaluation state via named transition", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const next = appShellReducer(initial, setEvaluationState({ dependencyLevel: 3 }));
    expect(next.stepRuns.evaluationState.dependencyLevel).toBe(3);
  });

  it("marks a run key as loading via named transition", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const next = appShellReducer(initial, setStepRunLoading("build"));
    expect(next.stepRuns.actionStates.build).toBe("loading");
  });

  it("clears loading and active run id when a cancel request is accepted", () => {
    const initial = appShellReducer(
      appShellReducer(createInitialState(toInitialSlices(buildRee())), setStepRunLoading("build")),
      setActiveRunId("build", "run-1"),
    );

    const next = appShellReducer(initial, cancelStepRun("build", "run-1"));

    expect(next.stepRuns.actionStates.build).toBeUndefined();
    expect(next.stepRuns.activeRunIds.build).toBeUndefined();
  });

  it("ignores stale step completion for a run that is no longer active", () => {
    const initial = appShellReducer(
      appShellReducer(createInitialState(toInitialSlices(buildRee())), setStepRunLoading("build")),
      setActiveRunId("build", "run-2"),
    );

    const next = appShellReducer(
      initial,
      completeStepRun({
        key: "build",
        runId: "run-1",
        actionState: "done",
        badge: "succeeded",
        timestamp: "2026-01-01T00:00:00Z",
      }),
    );

    expect(next).toBe(initial);
  });

  it("ignores stale source outcome for a run that is no longer active", () => {
    const initial = appShellReducer(
      appShellReducer(createInitialState(toInitialSlices(buildRee())), setStepRunLoading("source")),
      setActiveRunId("source", "run-2"),
    );

    const next = appShellReducer(initial, {
      type: "applySourceOutcome",
      outcome: {
        runId: "run-1",
        sourceSnapshotArchiveName: "repo.tar.gz",
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });

    expect(next).toBe(initial);
  });

  it("shows and clears toast via named transitions", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const shown = appShellReducer(initial, showToast({ message: "Saved", type: "success" }));
    expect(shown.uiChrome.toast).toEqual({ message: "Saved", type: "success" });
    const cleared = appShellReducer(shown, clearToast());
    expect(cleared.uiChrome.toast).toBeNull();
  });
});
