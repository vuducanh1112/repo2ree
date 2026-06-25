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

  it("maps container runtime_entry with phase overrides", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
        runtime_entry: { kind: "container", engine: "podman", overrides: { exec: "code/run" } },
      },
      fallbackName: "demo",
    });

    const entry = mapped.reeSpec.runtime_entry;
    expect(entry.kind).toBe("container");
    expect(entry.overrides).toEqual({ provision: "", exec: "code/run", teardown: "" });
  });

  it("defaults overrides to empty for legacy runtime_entry without the key", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: { runtime_entry: { kind: "container", engine: "docker" } },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.runtime_entry.overrides).toEqual({
      provision: "",
      exec: "",
      teardown: "",
    });
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
