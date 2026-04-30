import { describe, expect, it } from "vitest";
import type { Ree } from "../../domain/ree/ReeSpec";
import {
  applyWorkspaceEditorAction,
  createInitialWorkspaceEditorState,
} from "./WorkspaceEditorState";

function buildRee(): Ree {
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

describe("workspaceEditorState", () => {
  it("applies source patch outcomes to ree and source status metadata", () => {
    const initial = createInitialWorkspaceEditorState(buildRee());

    const next = applyWorkspaceEditorAction(initial, {
      type: "workspaceEditor/applySourcePatchOutcome",
      outcome: {
        reePatch: {
          origin_url: "https://example.org/repo.git",
          _sourceAvailable: true,
          _sourceAcquiredBy: "download",
        },
        immutableSourceSnapshotFiles: [{ id: "1", name: "README.md", type: "file" }],
        immutableSourceSnapshotArchiveName: "repo-original.tar.gz",
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });

    expect(next.ree.origin_url).toBe("https://example.org/repo.git");
    expect(next.ree._sourceAvailable).toBe(true);
    expect(next.actionStates.source).toBe("done");
    expect(next.badges.source).toBe(true);
    expect(next.timestamps.source).toBe("2026-01-01T00:00:00Z");
    expect(next.immutableSourceSnapshotArchiveName).toBe("repo-original.tar.gz");
  });

  it("records completion metadata for completed service runs", () => {
    const initial = createInitialWorkspaceEditorState(buildRee());

    const next = applyWorkspaceEditorAction(initial, {
      type: "workspaceEditor/completeWorkflowRun",
      completion: {
        key: "build",
        serviceLog: { lines: [{ type: "ok", msg: "done" }], ts: "2026-01-01T00:00:00Z" },
        actionState: "done",
        badge: true,
        timestamp: "2026-01-01T00:00:00Z",
      },
    });

    expect(next.serviceLogs.build?.lines[0]?.msg).toBe("done");
    expect(next.actionStates.build).toBe("done");
    expect(next.badges.build).toBe(true);
    expect(next.timestamps.build).toBe("2026-01-01T00:00:00Z");
  });

  it("resets workflow-dependent explorer state on source change", () => {
    const initial = {
      ...createInitialWorkspaceEditorState(buildRee()),
      actionStates: { build: "done" as const },
      badges: { build: true },
      timestamps: { build: "2026-01-01T00:00:00Z" },
      virtualFiles: [{ id: "1", name: "README.md", type: "file" as const }],
    };

    const next = applyWorkspaceEditorAction(initial, {
      type: "workspaceEditor/resetWorkflowOnSourceChange",
      serviceParams: initial.serviceParams,
    });

    expect(next.actionStates).toEqual({});
    expect(next.badges).toEqual({});
    expect(next.timestamps).toEqual({});
    expect(next.virtualFiles).toEqual([]);
    expect(next.ree.origin_url).toBe("");
    expect(next.ree._sourceAvailable).toBe(false);
  });
});
