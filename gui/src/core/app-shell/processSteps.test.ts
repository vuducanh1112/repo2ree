import { PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import type { StepEvidence } from "@core/ree/StepEvidence";
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { describe, expect, it } from "vitest";

function stepFor(key: string) {
  const step = PROCESS_STEPS.find((s) => s.key === key);
  if (!step) throw new Error(`No step for key ${key}`);
  return step;
}

// Doneness comes from the REE's audit, not from what this session ran, so every
// case below leaves `badges` empty — the state a freshly reloaded tab is in.
function reeWith(audit: StepEvidence) {
  return { ...createEmptyReeEditorViewModel(), audit };
}

const NO_BADGES = {} as Badges;

describe("executed step navCompleted", () => {
  const cases = [
    { page: PAGE.BUILD, step: "runtime" },
    { page: PAGE.SBOM, step: "sbom" },
    { page: PAGE.ACTIVATION, step: "test_activation" },
    { page: PAGE.EVALUATE, step: "evaluation" },
  ] as const;

  for (const { page, step } of cases) {
    it(`completes on current ${step} evidence, with no badge in this session`, () => {
      const ree = reeWith({ [step]: "current" });
      expect(resolveNavCompleted(stepFor(page), ree, NO_BADGES)).toBe(true);
    });

    it(`is not complete while ${step} evidence is missing`, () => {
      expect(resolveNavCompleted(stepFor(page), reeWith({}), NO_BADGES)).toBe(false);
    });

    // The receipt is still on the aggregate, but what it rests on has moved.
    // The step has to run again, so it does not read as done.
    it(`is not complete while ${step} evidence is stale`, () => {
      const ree = reeWith({ [step]: "stale" });
      expect(resolveNavCompleted(stepFor(page), ree, NO_BADGES)).toBe(false);
    });
  }

  it("ignores a session badge that the REE's own audit does not back", () => {
    const ree = reeWith({});
    expect(resolveNavCompleted(stepFor(PAGE.BUILD), ree, { build: true } as Badges)).toBe(false);
  });
});

describe("metadata step navCompleted", () => {
  const named = createEmptyReeEditorViewModel();
  named.spec.name = "python-hello-world";

  it("is not complete while a required field is empty", () => {
    expect(resolveNavCompleted(stepFor(PAGE.METADATA), named, NO_BADGES)).toBe(false);
  });

  it("completes once name, version and description are all filled", () => {
    const ree = createEmptyReeEditorViewModel();
    ree.spec.name = "python-hello-world";
    ree.spec.catalogMetadata.version = "1.0.0";
    ree.spec.catalogMetadata.description = "Reproduces the hello-world figure.";
    expect(resolveNavCompleted(stepFor(PAGE.METADATA), ree, NO_BADGES)).toBe(true);
  });
});

describe("deposit step navCompleted", () => {
  // Deposits have no audited receipt on the aggregate, so they stay session-badged.
  it("completes on any archive badge", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(resolveNavCompleted(stepFor(PAGE.ARCHIVE), ree, { zenodo: true } as Badges)).toBe(true);
    expect(resolveNavCompleted(stepFor(PAGE.ARCHIVE), ree, NO_BADGES)).toBe(false);
  });
});
