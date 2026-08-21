import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import { describe, expect, it, vi } from "vitest";
import { createHydrateReeWorkspace } from "./hydrateReeWorkspace";

describe("createHydrateReeWorkspace", () => {
  it("hydrates every editor slice and locks a sealed workspace", () => {
    const dispatch = vi.fn();
    const ree = mapRawReeIntentToSlices({
      reeIntent: { name: "Hydrated REE" },
      reeSession: {
        // biome-ignore lint/style/useNamingConvention: backend wire field
        sealed_at: "2026-01-01T00:00:00Z",
        // biome-ignore lint/style/useNamingConvention: backend wire field
        seal_hash: "sha256:abc",
      },
      fallbackName: "Fallback",
    });

    createHydrateReeWorkspace(dispatch)({ workspaceFiles: [], reeArtifactFiles: [], ree });

    expect(dispatch.mock.calls.map(([action]) => action.type)).toEqual([
      "updateReeSpec",
      "setWorkspaceSourceState",
      "setArtifactStatus",
      "setEvaluationState",
      "setLocked",
    ]);
    expect(dispatch.mock.calls[0][0].value({})).toBe(ree.reeSpec);
    expect(dispatch.mock.calls[1][0].value({})).toBe(ree.workspaceSourceState);
    expect(dispatch.mock.calls[2][0].value({})).toBe(ree.artifactStatus);
    expect(dispatch.mock.calls[3][0].value({})).toBe(ree.evaluationState);
    expect(dispatch.mock.calls[4][0]).toEqual({ type: "setLocked", value: true });
  });

  it("ignores file-only snapshots and preserves an existing seal", () => {
    const dispatch = vi.fn();
    const hydrate = createHydrateReeWorkspace(dispatch);
    hydrate({ workspaceFiles: [], reeArtifactFiles: [] });
    expect(dispatch).not.toHaveBeenCalled();

    const ree = mapRawReeIntentToSlices({ reeIntent: {}, reeSession: {}, fallbackName: "REE" });
    hydrate({ workspaceFiles: [], reeArtifactFiles: [], ree });
    const artifactAction = dispatch.mock.calls[2][0];
    const sealed = { sealedAt: "2026-01-01", sealHash: "hash", runtimeIncluded: true };
    expect(artifactAction.value(sealed)).toBe(sealed);
    expect(dispatch).toHaveBeenCalledTimes(4);
  });
});
