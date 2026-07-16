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
            run_script: "ree-scripts/experiments/benchmark.sh",
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
        runScript: "ree-scripts/experiments/benchmark.sh",
        verifyScript: "",
        outputPaths: [],
        runtimeEstimate: "15-20 min",
        resourceEstimates: {
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
        experiments: [{ name: "smoke", run_script: "ree-scripts/experiments/smoke.sh" }],
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.experiments).toEqual([
      {
        name: "smoke",
        description: "",
        runScript: "ree-scripts/experiments/smoke.sh",
        verifyScript: "",
        outputPaths: [],
        runtimeEstimate: "",
        resourceEstimates: {
          cpu: "",
          memory: "",
          gpu: "",
          storage: "",
          network: "",
        },
      },
    ]);
  });

  it("maps the activation run script from persisted intent", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
        activation: { run_script: "ree/custom-activation.sh" },
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.activation.runScript).toBe("ree/custom-activation.sh");
  });

  it("keeps the activation run script empty when not present in intent", () => {
    // The reserved path is backend-owned: intents arrive with it settled, and
    // an empty local value is normalized server-side on the next patch.
    const mapped = mapRawReeIntentToSlices({ reeIntent: {}, fallbackName: "demo" });

    expect(mapped.reeSpec.activation.runScript).toBe("");
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
