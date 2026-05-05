import { describe, expect, it } from "vitest";
import { appShellReducer, createInitialState } from "../../ui/app-shell/providers/AppShellProvider";
import {
  createEmptyReeEditorViewModel,
  type ReeEditorViewModel,
} from "../ree-editor/reeEditorViewModel";
import { patch } from "./actions";
import { createAppShellState } from "./appShellState";

function buildRee(): ReeEditorViewModel {
  return {
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
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
    sourceAvailable: false,
    sourceIncluded: false,
    runtimeIncluded: false,
    downloadableFiles: [],
    evalLevel: 0,
  };
}

function toInitialSlices(ree: ReeEditorViewModel) {
  return {
    reeSpec: {
      name: ree.name,
      origin_url: ree.origin_url,
      source_type: ree.source_type,
      runtime: ree.runtime,
      build_runtime_script: ree.build_runtime_script,
      activation_script: ree.activation_script,
      sbom: ree.sbom,
      swhid: ree.swhid,
      zenodo_doi: ree.zenodo_doi,
      dataverse_doi: ree.dataverse_doi,
      repro_level: ree.repro_level,
      detected_dependencies: ree.detected_dependencies,
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
      downloadableFiles: ree.downloadableFiles,
      sealedAt: ree.sealedAt,
      sealHash: ree.sealHash,
    },
    evaluationState: {
      evalLevel: ree.evalLevel,
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
        workspaceSourceState: {
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

    expect(next.reeDraft.reeSpec.origin_url).toBe("https://example.org/repo.git");
    expect(next.reeDraft.workspaceSourceState.sourceAvailable).toBe(true);
    expect(next.workflowRun.actionStates.source).toBe("done");
    expect(next.workflowRun.badges.source).toBe(true);
    expect(next.workflowRun.timestamps.source).toBe("2026-01-01T00:00:00Z");
    expect(next.reeDraft.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
    expect(view.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
  });

  it("records completion metadata for completed workflow runs", () => {
    const initial = createInitialState(toInitialSlices(buildRee()));

    const next = appShellReducer(initial, {
      type: "completeWorkflowRun",
      completion: {
        key: "build",
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });

    expect(next.workflowRun.actionStates.build).toBe("done");
    expect(next.workflowRun.badges.build).toBe(true);
    expect(next.workflowRun.timestamps.build).toBe("2026-01-01T00:00:00Z");
  });

  it("resets workflow-dependent workspace state on source change", () => {
    const initial = {
      ...createInitialState(toInitialSlices(buildRee())),
      workflowRun: {
        ...createInitialState(toInitialSlices(buildRee())).workflowRun,
        actionStates: { build: "done" as const },
        badges: { build: true },
        timestamps: { build: "2026-01-01T00:00:00Z" },
      },
    };

    const next = appShellReducer(initial, {
      type: "resetWorkflowOnSourceChange",
      workflowParams: initial.workflowRun.workflowParams,
    });

    expect(next.workflowRun.actionStates).toEqual({});
    expect(next.workflowRun.badges).toEqual({});
    expect(next.workflowRun.timestamps).toEqual({});
    expect(next.reeDraft.reeSpec.origin_url).toBe("");
    expect(next.reeDraft.workspaceSourceState.sourceAvailable).toBe(false);
  });

  it("keeps the aggregate selector aligned with the slice state", () => {
    const state = createInitialState(toInitialSlices(buildRee()));

    const view = createAppShellState(state);

    expect(view.page).toBe(state.uiChrome.page);
    expect(view.workflowParams).toBe(state.workflowRun.workflowParams);
    expect(view.locked).toBe(state.reeDraft.locked);
    expect(createEmptyReeEditorViewModel().name).toBe("");
  });

  it("updates ree metadata without mutating source or artifact slices", () => {
    const initial = createInitialState(
      toInitialSlices({
        ...buildRee(),
        sourceAvailable: true,
        sourceIncluded: true,
        runtimeIncluded: true,
        downloadableFiles: ["runtime.tar.gz"],
      }),
    );

    const next = appShellReducer(
      initial,
      patch("reeDraft", {
        reeSpec: {
          ...initial.reeDraft.reeSpec,
          name: "renamed",
        },
      }),
    );

    expect(next.reeDraft.reeSpec.name).toBe("renamed");
    expect(next.reeDraft.workspaceSourceState).toEqual(initial.reeDraft.workspaceSourceState);
    expect(next.reeDraft.artifactStatus).toEqual(initial.reeDraft.artifactStatus);
  });
});
