import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import { describe, expect, it, vi } from "vitest";
import { createHydrateReeWorkspace } from "./hydrateReeWorkspace";

describe("createHydrateReeWorkspace", () => {
  it("hydrates only the editable definition draft", () => {
    const dispatch = vi.fn();
    const ree = mapRawReeIntentToSlices({
      reeIntent: { name: "Hydrated REE" },
      reeSession: {
        // biome-ignore lint/style/useNamingConvention: backend wire field
        sealed_at: "2026-01-01T00:00:00Z",
        // biome-ignore lint/style/useNamingConvention: backend wire field
        seal_hash: "sha256:abc",
      },
      audit: { runtime: { evidence: "current", payload: "present" } },
      fallbackName: "Fallback",
    });

    createHydrateReeWorkspace(dispatch)({ workspaceFiles: [], reeArtifactFiles: [], ree });

    expect(dispatch.mock.calls.map(([action]) => action.type)).toEqual(["updateReeSpec"]);
    expect(dispatch.mock.calls[0][0].value({})).toBe(ree.reeSpec);
  });

  it("ignores file-only snapshots", () => {
    const dispatch = vi.fn();
    const hydrate = createHydrateReeWorkspace(dispatch);
    hydrate({ workspaceFiles: [], reeArtifactFiles: [] });
    expect(dispatch).not.toHaveBeenCalled();

    const ree = mapRawReeIntentToSlices({ reeIntent: {}, reeSession: {}, fallbackName: "REE" });
    hydrate({ workspaceFiles: [], reeArtifactFiles: [], ree });
    expect(dispatch).toHaveBeenCalledTimes(1);
  });
});
