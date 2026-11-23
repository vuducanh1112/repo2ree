import { PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { describe, expect, it } from "vitest";
import { authoringProgress } from "../../../tests/support/authoringProgress";

function stepFor(key: string) {
  const step = PROCESS_STEPS.find((s) => s.key === key);
  if (!step) throw new Error(`No step for key ${key}`);
  return step;
}

function reeWhere(statuses: Parameters<typeof authoringProgress>[0]) {
  return { ...createEmptyReeEditorViewModel(), steps: authoringProgress(statuses) };
}

const NO_BADGES = {} as Badges;

describe("authoring step navCompleted", () => {
  const cases = [
    { page: PAGE.ACQUIRE_SOURCE, step: "acquire_source" },
    { page: PAGE.METADATA, step: "metadata" },
    { page: PAGE.OBSERVE_HARDWARE, step: "observe_hardware" },
    { page: PAGE.EVALUATE_REPRODUCIBILITY, step: "evaluate_reproducibility" },
    { page: PAGE.BUILD_EXPERIMENT_ENVIRONMENT, step: "build_experiment_environment" },
    { page: PAGE.GENERATE_SBOM, step: "generate_sbom" },
    { page: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT, step: "activate_experiment_environment" },
    { page: PAGE.EXPERIMENTS, step: "experiments" },
    { page: PAGE.SEAL_REE, step: "seal_ree" },
  ] as const;

  for (const { page, step } of cases) {
    it(`completes when the REE says ${step} is complete`, () => {
      expect(resolveNavCompleted(stepFor(page), reeWhere({ [step]: "complete" }), NO_BADGES)).toBe(
        true,
      );
    });

    it(`is not complete while the REE says ${step} is ready`, () => {
      expect(resolveNavCompleted(stepFor(page), reeWhere({ [step]: "ready" }), NO_BADGES)).toBe(
        false,
      );
    });
  }

  it("ignores a session badge that the REE does not back", () => {
    expect(
      resolveNavCompleted(stepFor(PAGE.BUILD_EXPERIMENT_ENVIRONMENT), reeWhere({}), {
        [PAGE.BUILD_EXPERIMENT_ENVIRONMENT]: true,
      } as Badges),
    ).toBe(false);
  });
});

describe("deposit step navCompleted", () => {
  it("completes on any archive badge", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(resolveNavCompleted(stepFor(PAGE.ARCHIVE), ree, { zenodo: true } as Badges)).toBe(true);
    expect(resolveNavCompleted(stepFor(PAGE.ARCHIVE), ree, NO_BADGES)).toBe(false);
  });
});
