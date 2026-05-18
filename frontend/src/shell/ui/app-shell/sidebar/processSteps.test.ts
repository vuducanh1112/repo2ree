import { describe, expect, it } from "vitest";
import type { Badges } from "../../../../core/ree/ReeTypes";
import { createEmptyReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { runtimeNavCompleted } from "./processSteps";

describe("runtimeNavCompleted", () => {
  it("uses completed build, sbom, and activation badges when present", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(runtimeNavCompleted(ree, { build: true, sbom: true, activation: true } as Badges)).toBe(
      true,
    );
  });

  it("uses durable runtime, sbom, and activation metadata after reload/import", () => {
    const ree = {
      ...createEmptyReeEditorViewModel(),
      runtime: "runtime.tar.gz",
      sbom: "sbom.json",
      activation_script: "activation_test.sh",
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
      sbom: "sbom.json",
    };

    expect(runtimeNavCompleted(ree, {} as Badges)).toBe(false);
  });
});
