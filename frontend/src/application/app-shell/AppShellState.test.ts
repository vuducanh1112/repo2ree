import { describe, expect, it } from "vitest";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import { appShellReducer, createInitialState } from "../../ui/app-shell/providers/AppShellProvider";
import { appShellSelectors } from "./AppShellSelectors";

function buildRee(): ReeDraftViewModel {
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
  };
}

describe("appShellState", () => {
  it("applies source patch outcomes to ree and source status metadata", () => {
    const initial = createInitialState(buildRee());

    const next = appShellReducer(initial, {
      type: "appShell/applySourceOutcome",
      outcome: {
        reeSpecPatch: {
          origin_url: "https://example.org/repo.git",
        },
        workspaceSourceState: {
          sourceAvailable: true,
          sourceAcquiredBy: "download",
        },
        sourceSnapshotFiles: [{ id: "1", name: "README.md", type: "file" }],
        sourceSnapshotArchiveName: "repo-original.tar.gz",
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });
    const view = appShellSelectors.state(next);

    expect(next.reeDraft.reeSpec.origin_url).toBe("https://example.org/repo.git");
    expect(next.workspaceRemote.workspaceSourceState.sourceAvailable).toBe(true);
    expect(next.workflowRun.actionStates.source).toBe("done");
    expect(next.workflowRun.badges.source).toBe(true);
    expect(next.workflowRun.timestamps.source).toBe("2026-01-01T00:00:00Z");
    expect(next.workspaceRemote.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
    expect(view.sourceSnapshotArchiveName).toBe("repo-original.tar.gz");
  });

  it("records completion metadata for completed workflow runs", () => {
    const initial = createInitialState(buildRee());

    const next = appShellReducer(initial, {
      type: "appShell/completeWorkflowRun",
      completion: {
        key: "build",
        workflowLog: { lines: [{ type: "ok", msg: "done" }], ts: "2026-01-01T00:00:00Z" },
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });

    expect(next.workflowRun.workflowLogs.build?.lines[0]?.msg).toBe("done");
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
      workspaceRemote: {
        ...createInitialState(buildRee()).workspaceRemote,
        workspaceFiles: [{ id: "1", name: "README.md", type: "file" as const }],
      },
    };

    const next = appShellReducer(initial, {
      type: "appShell/resetWorkflowOnSourceChange",
      workflowParams: initial.workflowRun.workflowParams,
    });

    expect(next.workflowRun.actionStates).toEqual({});
    expect(next.workflowRun.badges).toEqual({});
    expect(next.workflowRun.timestamps).toEqual({});
    expect(next.workspaceRemote.workspaceFiles).toEqual([]);
    expect(next.reeDraft.reeSpec.origin_url).toBe("");
    expect(next.workspaceRemote.workspaceSourceState.sourceAvailable).toBe(false);
  });

  it("keeps the aggregate selector aligned with the slice state", () => {
    const state = createInitialState(buildRee());

    const view = appShellSelectors.state(state);

    expect(view.page).toBe(state.uiChrome.page);
    expect(view.workflowParams).toBe(state.workflowRun.workflowParams);
    expect(view.workspaceFiles).toBe(state.workspaceRemote.workspaceFiles);
    expect(view.ree.name).toBe(state.reeDraft.reeSpec.name);
    expect(view.ree.sourceAvailable).toBe(
      state.workspaceRemote.workspaceSourceState.sourceAvailable ?? false,
    );
  });
});
