import { PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import { describe, expect, it } from "vitest";
import { authoringProgress } from "../../../tests/support/authoringProgress";
import type { EvidenceStep } from "../ree/StepEvidence";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "../ree-editor/reeEditorViewModel";
import { buildSealStepItems, SEAL_STEPS } from "./sealSteps";

const activationStep: EvidenceStep = "activate_experiment_environment";

function halfAuthoredRee() {
  return patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
    spec: {
      name: "Reproducible experiment",
      experimentEnvironmentPath: "artifacts/climate-runtime.tar",
      swhid: "swh:1:dir:abc",
      sbom: "artifacts/sbom.json",
    },
    source: { sourceAvailable: true },
    audit: { evaluate_reproducibility: "current", [activationStep]: "current" },
  });
}

describe("buildSealStepItems", () => {
  it("agrees with the authoring rail on every step-backed entry", () => {
    const ree = halfAuthoredRee();
    const badges: Badges = {};
    const doneByKey = Object.fromEntries(
      buildSealStepItems(ree, badges).map((item) => [item.key, item.done]),
    );

    for (const entry of SEAL_STEPS) {
      if (!entry.page) continue;
      const step = PROCESS_STEPS.find((candidate) => candidate.key === entry.page);
      if (!step) throw new Error(`no process step for ${entry.key}`);
      expect(doneByKey[entry.key]).toBe(resolveNavCompleted(step, ree, badges));
    }
  });

  it("reads the one non-step entry off the spec", () => {
    const ree = halfAuthoredRee();
    const done = (model: typeof ree) =>
      buildSealStepItems(model, {}).find((item) => item.key === "swh")?.done;

    expect(done(ree)).toBe(true);
    expect(done(patchReeEditorViewModel(ree, { spec: { swhid: "" } }))).toBe(false);
  });

  it.each([
    [
      PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
      "experimentEnvironmentPath",
      "artifacts/climate-runtime.tar",
    ],
    [PAGE.GENERATE_SBOM, "sbom", "artifacts/sbom.json"],
  ])("does not call %s done on a declaration with no receipt", (key, field, declaration) => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: { [field]: declaration },
      audit: {},
    });

    const item = buildSealStepItems(ree, {}).find((entry) => entry.key === key);
    expect(item?.done).toBe(false);
  });

  it("counts metadata done when the REE says so", () => {
    const metadata = (statuses: Parameters<typeof authoringProgress>[0]) =>
      buildSealStepItems(
        { ...createEmptyReeEditorViewModel(), steps: authoringProgress(statuses) },
        {},
      ).find((item) => item.key === "metadata")?.done;

    expect(metadata({ metadata: "ready" })).toBe(false);
    expect(metadata({ metadata: "complete" })).toBe(true);
  });

  it("carries an experiments entry and no unachievable archive entry", () => {
    const keys = buildSealStepItems(createEmptyReeEditorViewModel(), {}).map((item) => item.key);

    expect(keys).toContain("experiments");
    expect(keys).not.toContain("archive");
  });
});
