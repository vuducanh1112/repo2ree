import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import { patchCatalogMetadata } from "@core/ree/catalogMetadataOps";
import type { Badges } from "@core/ree/ReeTypes";
import { describe, expect, it } from "vitest";
import type { EvidenceStep } from "../ree/StepEvidence";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "../ree-editor/reeEditorViewModel";
import { buildSealStepItems, SEAL_STEPS } from "./sealSteps";

const activationStep: EvidenceStep = "test_activation";

/** Half-authored: some steps hold a receipt, some only a declaration. */
function halfAuthoredRee() {
  return patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
    spec: {
      name: "Reproducible experiment",
      runtime: "artifacts/climate-runtime.tar",
      swhid: "swh:1:dir:abc",
      sbom: "artifacts/sbom.json",
    },
    source: { sourceAvailable: true },
    audit: { evaluation: "current", [activationStep]: "current" },
  });
}

describe("buildSealStepItems", () => {
  // The invariant the seal page exists to keep: it projects the authoring
  // steps, and never holds a second opinion about them.
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

  // The drift this file used to pin: a declared path is not a built runtime.
  it.each([
    ["runtime", "artifacts/climate-runtime.tar"],
    ["sbom", "artifacts/sbom.json"],
  ])("does not call %s done on a declaration with no receipt", (key, declaration) => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: { [key]: declaration },
      audit: {},
    });

    const item = buildSealStepItems(ree, {}).find((entry) => entry.key === key);
    expect(item?.done).toBe(false);
  });

  it("requires the metadata the metadata page marks required", () => {
    const named = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: { name: "Named only" },
    });
    const metadata = (model: typeof named) =>
      buildSealStepItems(model, {}).find((item) => item.key === "metadata")?.done;

    expect(metadata(named)).toBe(false);
    expect(
      metadata(
        patchReeEditorViewModel(named, {
          spec: patchCatalogMetadata(named.spec, {
            version: "1.0.0",
            description: "Describes the REE",
          }),
        }),
      ),
    ).toBe(true);
  });

  // Experiments are the REE's scientific payload; the seal used to be silent
  // about them while warning about a deposit it could never satisfy.
  it("carries an experiments entry and no unachievable archive entry", () => {
    const keys = buildSealStepItems(createEmptyReeEditorViewModel(), {}).map((item) => item.key);

    expect(keys).toContain("experiments");
    expect(keys).not.toContain("archive");
  });
});
