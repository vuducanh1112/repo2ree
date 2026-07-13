import { describe, expect, it } from "vitest";
import { planManualArtifactCompletion } from "./manualArtifactUpdatePlanning";

describe("planManualArtifactCompletion", () => {
  it("locks the workspace for create", () => {
    const result = planManualArtifactCompletion({ key: "create" });

    expect(result.lock).toBe(true);
    expect(result.successMessage).toContain("fields locked");
  });

  it("returns ree spec patches for archive completion actions", () => {
    expect(
      planManualArtifactCompletion({ key: "swh", generatedSwhid: "swh:1:dir:abc" }).reeSpecPatch
        ?.swhid,
    ).toBe("swh:1:dir:abc");
    expect(
      planManualArtifactCompletion({ key: "zenodo", generatedZenodoDoi: "10.5281/zenodo.123" })
        .reeSpecPatch?.zenodoDoi,
    ).toBe("10.5281/zenodo.123");
    expect(
      planManualArtifactCompletion({
        key: "dataverse",
        generatedDataverseDoi: "doi:10.5072/DVN/123456",
      }).reeSpecPatch?.dataverseDoi,
    ).toBe("doi:10.5072/DVN/123456");
  });

  it("falls back to a generic completion message", () => {
    const result = planManualArtifactCompletion({ key: "unknown" });

    expect(result.successMessage).toBe("unknown completed");
  });
});
