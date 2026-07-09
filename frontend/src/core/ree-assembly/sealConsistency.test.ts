import { describe, expect, it } from "vitest";
import { type ConsistencyReport, staleAssemblyStepKeys, staleSealItems } from "./sealConsistency";

const report: ConsistencyReport = {
  steps: [
    {
      step: "build_runtime",
      status: "stale",
      runId: "run-b",
      recordedAt: "2026-01-01T00:00:00Z",
      staleInputs: [
        { input: "buildScript", recorded: "sha256:aa", current: "sha256:bb" },
        { input: "runtimeArtifact", recorded: "sha256:cc", current: null },
      ],
    },
    { step: "generate_sbom", status: "missing" },
    { step: "activation_test", status: "fresh", runId: "run-a", staleInputs: [] },
    {
      step: "experiment:fig 2",
      status: "stale",
      runId: "run-e",
      staleInputs: [{ input: "verifyScript", recorded: "sha256:dd", current: "sha256:ee" }],
    },
  ],
};

describe("staleSealItems", () => {
  it("lists only stale steps, with human labels and named moved inputs", () => {
    expect(staleSealItems(report)).toEqual([
      {
        key: "build_runtime",
        label: "Build",
        detail: "build script changed, runtime artifact changed",
      },
      {
        key: "experiment:fig 2",
        label: "Experiment “fig 2”",
        detail: "verify script changed",
      },
    ]);
  });

  it("is empty without a report or without stale steps", () => {
    expect(staleSealItems(undefined)).toEqual([]);
    expect(staleSealItems({ steps: [{ step: "build_runtime", status: "fresh" }] })).toEqual([]);
  });

  it("falls back to a generic detail for unknown inputs and empty slices", () => {
    const items = staleSealItems({
      steps: [
        {
          step: "build_runtime",
          status: "stale",
          staleInputs: [{ input: "somethingNew", recorded: null, current: "sha256:ff" }],
        },
        { step: "generate_sbom", status: "stale" },
      ],
    });
    expect(items[0].detail).toBe("somethingNew changed");
    expect(items[1].detail).toBe("inputs changed since the recorded run");
  });
});

describe("staleAssemblyStepKeys", () => {
  it("maps stale steps to assembly keys, folding experiments into one node", () => {
    expect(staleAssemblyStepKeys(report)).toEqual(new Set(["build", "experiments"]));
  });

  it("ignores fresh and missing steps", () => {
    expect(
      staleAssemblyStepKeys({ steps: [{ step: "generate_sbom", status: "missing" }] }),
    ).toEqual(new Set());
    expect(staleAssemblyStepKeys(undefined)).toEqual(new Set());
  });
});
