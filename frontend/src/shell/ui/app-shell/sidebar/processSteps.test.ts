import { describe, expect, it } from "vitest";
import type { Badges } from "../../../../core/ree/ReeTypes";
import { createEmptyReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { runtimeNavCompleted } from "./processSteps";

describe("runtimeNavCompleted", () => {
  it("uses completed build and sbom badges when present", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(runtimeNavCompleted(ree, { build: true, sbom: true } as Badges)).toBe(true);
  });

  it("uses durable runtime and sbom metadata after reload/import", () => {
    const ree = {
      ...createEmptyReeEditorViewModel(),
      runtime: "runtime.tar.gz",
      sbom: "sbom.json",
    };

    expect(runtimeNavCompleted(ree, {} as Badges)).toBe(true);
  });

  it("ignores skipped sentinels in durable metadata", () => {
    const ree = {
      ...createEmptyReeEditorViewModel(),
      runtime: "__skipped__",
      sbom: "sbom.json",
    };

    expect(runtimeNavCompleted(ree, {} as Badges)).toBe(false);
  });

  it("requires both runtime and sbom durable metadata", () => {
    const ree = {
      ...createEmptyReeEditorViewModel(),
      runtime: "runtime.tar.gz",
    };

    expect(runtimeNavCompleted(ree, {} as Badges)).toBe(false);
  });
});
