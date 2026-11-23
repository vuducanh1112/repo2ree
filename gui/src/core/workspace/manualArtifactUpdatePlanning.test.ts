import { describe, expect, it } from "vitest";
import { planManualArtifactCompletion } from "./manualArtifactUpdatePlanning";

describe("planManualArtifactCompletion", () => {
  it("locks the workspace for create", () => {
    const result = planManualArtifactCompletion({ key: "create" });

    expect(result.lock).toBe(true);
    expect(result.successMessage).toContain("fields locked");
  });

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
