import { describe, expect, it } from "vitest";
import { planManualArtifactCompletion } from "./manualArtifactUpdatePlanning";

describe("planManualArtifactCompletion", () => {
  it("locks the workspace for create", () => {
    const result = planManualArtifactCompletion({ key: "create" });

    expect(result.lock).toBe(true);
    expect(result.successMessage).toContain("fields locked");
  });

  // A deposit identifier names a deposit of a sealed REE, not the REE, so it is
  // recorded server-side as an archive-binding attestation. These steps used to
  // synthesize one locally and patch it onto the spec, which made the UI assert
  // an archival relationship that had never happened.
  it("patches nothing onto the spec for archive completion actions", () => {
    for (const key of ["swh", "zenodo", "dataverse"]) {
      expect(planManualArtifactCompletion({ key }).reeSpecPatch).toBeUndefined();
    }
  });

  it("falls back to a generic completion message", () => {
    const result = planManualArtifactCompletion({ key: "unknown" });

    expect(result.successMessage).toBe("unknown completed");
  });
});
