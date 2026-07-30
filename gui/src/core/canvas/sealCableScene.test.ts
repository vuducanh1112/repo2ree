import { describe, expect, it } from "vitest";
import { createEmptyReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import { buildSealCableItems } from "./sealCableScene";

describe("buildSealCableItems", () => {
  it("projects domain state into cable liveness", () => {
    const ree = {
      ...createEmptyReeEditorViewModel(),
      name: "Reproducible experiment",
      sourceAvailable: true,
      runtime: "python:3.13",
      swhid: "swh:1:dir:abc",
      sbom: "artifacts/sbom.json",
    };

    const items = buildSealCableItems(ree, { evaluate: true, activation: true });
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
