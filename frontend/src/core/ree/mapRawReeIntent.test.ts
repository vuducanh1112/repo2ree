import { describe, expect, it } from "vitest";
import { mapRawReeIntentToSlices } from "./mapRawReeIntent";

describe("mapRawReeIntentToSlices", () => {
  it("hydrates experiment estimates from persisted intent", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
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
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
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

  it("reads source_included and runtime_included from session", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {},
      reeSession: { source_available: true, source_included: true, runtime_included: false },
      fallbackName: "demo",
    });

    expect(mapped.workspaceSourceState.sourceIncluded).toBe(true);
    expect(mapped.artifactStatus.runtimeIncluded).toBe(false);
    expect(mapped.workspaceSourceState.sourceAvailable).toBe(true);
  });
});
