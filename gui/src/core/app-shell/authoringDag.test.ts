import { describe, expect, it } from "vitest";
import { authoringPageForStep } from "./authoringDag";
import { PAGE } from "./pages";

describe("authoring DAG", () => {
  it("routes the cross-check to its SBOM authoring surface", () => {
    expect(authoringPageForStep("crosscheck")).toBe(PAGE.SBOM);
    expect(authoringPageForStep("build_experiment_environment")).toBe(
      PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
    );
  });
});
