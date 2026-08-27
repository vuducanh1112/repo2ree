import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import { patchCatalogMetadata } from "@core/ree/catalogMetadataOps";
import type { Badges } from "@core/ree/ReeTypes";
import { describe, expect, it } from "vitest";
import type { EvidenceStep } from "../ree/StepEvidence";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "../ree-editor/reeEditorViewModel";
import { buildSealCableItems, SEAL_CABLES } from "./sealCableScene";

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

describe("buildSealCableItems", () => {
  // The invariant the seal panel exists to keep: a cable is a projection of an
  // authoring step, never a second opinion about it.
  it("agrees with the authoring rail on every step-backed cable", () => {
    const ree = halfAuthoredRee();
    const badges: Badges = {};
    const liveByKey = Object.fromEntries(
      buildSealCableItems(ree, badges).map((item) => [item.key, item.live]),
    );

    for (const cable of SEAL_CABLES) {
      if (!cable.page) continue;
      const step = PROCESS_STEPS.find((candidate) => candidate.key === cable.page);
      if (!step) throw new Error(`no process step for cable ${cable.key}`);
      expect(liveByKey[cable.key]).toBe(resolveNavCompleted(step, ree, badges));
    }
  });

  it("reads the one non-step cable off the spec", () => {
    const ree = halfAuthoredRee();
    const live = (model: typeof ree) =>
      buildSealCableItems(model, {}).find((item) => item.key === "swh")?.live;

    expect(live(ree)).toBe(true);
    expect(live(patchReeEditorViewModel(ree, { spec: { swhid: "" } }))).toBe(false);
  });

  // The drift this file used to pin: a declared path is not a built runtime.
  it.each([
    ["runtime", "artifacts/climate-runtime.tar"],
    ["sbom", "artifacts/sbom.json"],
  ])("does not call %s connected on a declaration with no receipt", (key, declaration) => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: { [key]: declaration },
      audit: {},
    });

    const cable = buildSealCableItems(ree, {}).find((item) => item.key === key);
    expect(cable?.live).toBe(false);
  });

  it("requires the metadata the metadata page marks required", () => {
    const named = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: { name: "Named only" },
    });
    const metadata = (model: typeof named) =>
      buildSealCableItems(model, {}).find((item) => item.key === "metadata")?.live;

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

  // Experiments are the REE's scientific payload; the preflight used to be
  // silent about them while warning about a deposit it could never satisfy.
  it("carries an experiments cable and no unachievable archive cable", () => {
    const keys = buildSealCableItems(createEmptyReeEditorViewModel(), {}).map((item) => item.key);

    expect(keys).toContain("experiments");
    expect(keys).not.toContain("archive");
  });
});
