import { describe, expect, it } from "vitest";
import type { EvidenceStep } from "../ree/StepEvidence";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "../ree-editor/reeEditorViewModel";
import { buildSealCableItems } from "./sealCableScene";

const activationStep: EvidenceStep = "test_activation";

describe("buildSealCableItems", () => {
  it("projects domain state into cable liveness", () => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: {
        name: "Reproducible experiment",
        runtime: "python:3.13",
        swhid: "swh:1:dir:abc",
        sbom: "artifacts/sbom.json",
      },
      source: { sourceAvailable: true },
      audit: { evaluation: "current", [activationStep]: "current" },
    });

    const items = buildSealCableItems(ree);
    const liveByKey = Object.fromEntries(items.map((item) => [item.key, item.live]));

    expect(liveByKey).toMatchObject({
      metadata: true,
      source: true,
      runtime: true,
      swh: true,
      sbom: true,
      evaluate: true,
      activation: true,
      archive: false,
    });
  });
});
