import type { Badges } from "@core/ree/ReeTypes";
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { describe, expect, it } from "vitest";
import { PAGE } from "../state/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "./processSteps";

function stepFor(key: string) {
  const step = PROCESS_STEPS.find((s) => s.key === key);
  if (!step) throw new Error(`No step for key ${key}`);
  return step;
}

describe("build step navCompleted", () => {
  it("completes when the build badge is present", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(resolveNavCompleted(stepFor(PAGE.BUILD), ree, { build: true } as Badges)).toBe(true);
  });

  it("is not complete without the build badge", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(resolveNavCompleted(stepFor(PAGE.BUILD), ree, {} as Badges)).toBe(false);
  });
});

describe("sbom step navCompleted", () => {
  it("completes when the sbom badge is present", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(resolveNavCompleted(stepFor(PAGE.SBOM), ree, { sbom: true } as Badges)).toBe(true);
  });
});

describe("activation step navCompleted", () => {
  it("completes when the activation badge is present", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(resolveNavCompleted(stepFor(PAGE.ACTIVATION), ree, { activation: true } as Badges)).toBe(
      true,
    );
  });
});
