import { describe, expect, it } from "vitest";
import { mapRawReeDraftToSlices } from "./mapRawReeDraft";

describe("mapRawReeDraftToSlices", () => {
  it("hydrates experiment estimates from persisted drafts", () => {
    const mapped = mapRawReeDraftToSlices({
      reeDraft: {
        experiments: [
          {
            name: "benchmark",
            description: "Measure throughput",
            command: "python bench.py",
            runtime_estimate: "15-20 min",
            resource_estimates: {
              cpu: "8 vCPU",
              memory: "16 GB",
              gpu: "1x A10",
              storage: "5 GB scratch",
              network: "offline",
            },
          },
        ],
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.experiments).toEqual([
      {
        name: "benchmark",
        description: "Measure throughput",
        command: "python bench.py",
        runtime_estimate: "15-20 min",
        resource_estimates: {
          cpu: "8 vCPU",
          memory: "16 GB",
          gpu: "1x A10",
          storage: "5 GB scratch",
          network: "offline",
        },
      },
    ]);
  });

  it("backfills missing experiment estimates with stable defaults", () => {
    const mapped = mapRawReeDraftToSlices({
      reeDraft: {
        experiments: [{ name: "smoke", command: "pytest -q" }],
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.experiments).toEqual([
      {
        name: "smoke",
        description: "",
        command: "pytest -q",
        runtime_estimate: "",
        resource_estimates: {
          cpu: "",
          memory: "",
          gpu: "",
          storage: "",
          network: "",
        },
      },
    ]);
  });
});
