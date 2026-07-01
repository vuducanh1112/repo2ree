import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import {
  createEmptyReeEditorViewModel,
  type ReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { describe, expect, it } from "vitest";
import {
  clearToast,
  completeAssemblyRun,
  resetAssemblyAfterSourceChange,
  setArtifactStatus,
  setAssemblyRunLoading,
  setEvaluationState,
  setWorkspaceSourceState,
  showToast,
  updateReeSpec,
} from "./actions";
import { appShellReducer, createInitialState } from "./appShellReducer";
import { createAppShellState } from "./appShellState";

function buildRee(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    name: "demo",
    sourceAvailable: false,
    sourceIncluded: false,
    runtimeIncluded: false,
    dependencyLevel: 0,
  };
}

function toInitialSlices(ree: ReeEditorViewModel) {
  return {
    reeSpec: {
      name: ree.name,
      catalog_metadata: ree.catalog_metadata,
      origin_url: ree.origin_url,
      source_type: ree.source_type,
      resolvedRevision: ree.resolvedRevision,
      runtime: ree.runtime,
      activation: ree.activation,
      sbom: ree.sbom,
      swhid: ree.swhid,
      zenodo_doi: ree.zenodo_doi,
      dataverse_doi: ree.dataverse_doi,
      experiments: ree.experiments,
      hardware_description: ree.hardware_description,
    },
    workspaceSourceState: {
      sourceAvailable: ree.sourceAvailable,
      sourceIncluded: ree.sourceIncluded,
      sourceAcquiredBy: ree.sourceAcquiredBy,
      uploadedArchive: ree.uploadedArchive,
      sourceSnapshotArchive: ree.sourceSnapshotArchive,
      sourceSnapshotCapturedAt: ree.sourceSnapshotCapturedAt,
    },
    artifactStatus: {
      runtimeIncluded: ree.runtimeIncluded,
      sealedAt: ree.sealedAt,
      sealHash: ree.sealHash,
    },
    evaluationState: {
      dependencyLevel: ree.dependencyLevel,
    },
  };
}

describe("appShellState", () => {
  it("applies source patch outcomes to ree and source status metadata", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));

    const next = appShellReducer(initial, {
      type: "applySourceOutcome",
      outcome: {
        reeSpecPatch: {
          origin_url: "https://example.org/repo.git",
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

    expect(next.reeIntent.reeSpec.origin_url).toBe("https://example.org/repo.git");
    expect(next.reeSession.workspaceSourceState.sourceAvailable).toBe(true);
    expect(next.assemblyRun.actionStates.source).toBe("done");
    expect(next.assemblyRun.badges.source).toBe(true);
    expect(next.assemblyRun.timestamps.source).toBe("2026-01-01T00:00:00Z");
    expect(next.uiChrome.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
    expect(view.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
  });

  it("records completion metadata for completed assembly runs", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));

    const next = appShellReducer(
      initial,
      completeAssemblyRun({
        key: "build",
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      }),
    );

    expect(next.assemblyRun.actionStates.build).toBe("done");
    expect(next.assemblyRun.badges.build).toBe(true);
    expect(next.assemblyRun.timestamps.build).toBe("2026-01-01T00:00:00Z");
  });

  it("resets assembly-dependent workspace state on source change", () => {
    const initial = {
      ...createInitialState(toInitialSlices(buildRee())),
      assemblyRun: {
        ...createInitialState(toInitialSlices(buildRee())).assemblyRun,
        actionStates: { build: "done" as const },
        badges: { build: true },
        timestamps: { build: "2026-01-01T00:00:00Z" },
      },
    };

    const next = appShellReducer(
      initial,
      resetAssemblyAfterSourceChange(initial.assemblyRun.assemblyOperationParams),
    );

    expect(next.assemblyRun.actionStates).toEqual({});
    expect(next.assemblyRun.badges).toEqual({});
    expect(next.assemblyRun.timestamps).toEqual({});
    expect(next.reeIntent.reeSpec.origin_url).toBe("");
    expect(next.reeSession.workspaceSourceState.sourceAvailable).toBe(false);
  });

  it("keeps the aggregate selector aligned with the slice state", () => {
    const state = createInitialState(toInitialSlices(buildRee()));

    const view = createAppShellState(state);

    expect(view.page).toBe(state.uiChrome.page);
    expect(view.assemblyOperationParams).toBe(state.assemblyRun.assemblyOperationParams);
    expect(view.locked).toBe(state.uiChrome.locked);
    expect(createEmptyReeEditorViewModel().name).toBe("");
  });

  it("updates ree metadata without mutating source or artifact slices", () => {
    const initial = createInitialState(
      toInitialSlices({
        ...buildRee(),
        sourceAvailable: true,
        sourceIncluded: true,
        runtimeIncluded: true,
      }),
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
    expect(next.assemblyRun.evaluationState.dependencyLevel).toBe(3);
  });

  it("marks a run key as loading via named transition", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const next = appShellReducer(initial, setAssemblyRunLoading("build"));
    expect(next.assemblyRun.actionStates.build).toBe("loading");
  });

  it("shows and clears toast via named transitions", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));
    const shown = appShellReducer(initial, showToast({ message: "Saved", type: "success" }));
    expect(shown.uiChrome.toast).toEqual({ message: "Saved", type: "success" });
    const cleared = appShellReducer(shown, clearToast());
    expect(cleared.uiChrome.toast).toBeNull();
  });
});
