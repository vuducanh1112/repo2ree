import { describe, expect, it } from "vitest";
import { addExperiment } from "./experimentOps";
import { createEmptyReeSpec } from "./ReeSpec";

describe("addExperiment", () => {
  it("creates experiments with empty runtime and resource estimates", () => {
    const updated = addExperiment(createEmptyReeSpec());

    expect(updated.experiments).toEqual([
      {
        name: "",
        description: "",
        run_script: "",
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
