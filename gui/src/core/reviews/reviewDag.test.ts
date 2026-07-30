import { describe, expect, it } from "vitest";
import { reviewLifecycleOrder, reviewStep, settledReviewStepCount } from "./reviewDag";

describe("reviewDag", () => {
  it("orders every dependency before the step that consumes it", () => {
    const order = reviewLifecycleOrder();

    for (const key of order) {
      const stepIndex = order.indexOf(key);
      for (const dependency of reviewStep(key).dependencies) {
        expect(order.indexOf(dependency)).toBeLessThan(stepIndex);
      }
    }
  });

  it("counts terminal evidentiary steps, including differences and failures", () => {
    expect(
      settledReviewStepCount({
        source: "succeeded",
        build: "running",
        activation: "failed",
        experiments: "different",
      }),
    ).toBe(3);
  });
});
