import { describe, expect, it } from "vitest";
import { createEmptyReeViewState, type ReeViewState } from "../../domain/ree/ReeViewState";
import { appShellReducer, createInitialState } from "../../ui/app-shell/providers/AppShellProvider";
import { createAppShellState } from "./AppShellState";

function buildRee(): ReeViewState {
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

describe("appShellState", () => {
  it("applies source patch outcomes to ree and source status metadata", () => {
    const initial = createInitialState(buildRee());

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
    const initial = createInitialState(buildRee());

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
      ...createInitialState(buildRee()),
      workflowRun: {
        ...createInitialState(buildRee()).workflowRun,
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
    const state = createInitialState(buildRee());

    const view = createAppShellState(state);

    expect(view.page).toBe(state.uiChrome.page);
    expect(view.workflowParams).toBe(state.workflowRun.workflowParams);
    expect(view.locked).toBe(state.reeDraft.locked);
    expect(createEmptyReeViewState().name).toBe("");
  });
});
