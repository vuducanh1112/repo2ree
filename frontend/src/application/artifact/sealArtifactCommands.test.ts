import { describe, expect, it } from "vitest";
import { planSealArtifactCommands } from "./sealArtifactCommands";

describe("planSealArtifactCommands", () => {
  it("plans REE patch, lock, and success toast in order", () => {
    expect(
      planSealArtifactCommands({
        sealedAt: "2026-04-29T09:00:00.000Z",
        sealHash: "sha256:abc123",
      }),
    ).toEqual([
      {
        type: "patchRee",
        patch: {
          _sealedAt: "2026-04-29T09:00:00.000Z",
          _sealHash: "sha256:abc123",
        },
      },
      { type: "setLocked", locked: true },
      { type: "toast", message: "REE sealed — now read-only", toastType: "success" },
    ]);
  });
});
