import { describe, expect, it } from "vitest";
import { exampleEditorRee } from "../../../tests/support/stepPageFixture";
import { type AuthoringStep, authoringPageForStep, authoringStepStatuses } from "./authoringDag";
import { PAGE } from "./pages";

const steps: AuthoringStep[] = [
  { key: "source", order: 1, label: "Source", requires: [], actions: [] },
  { key: "build", order: 2, label: "Build", requires: ["source"], actions: [] },
  { key: "crosscheck", order: 3, label: "Cross-check", requires: ["build"], actions: [] },
];

describe("authoring DAG", () => {
  it("derives readiness from catalog edges and current REE evidence", () => {
    const withoutSource = {
      ...exampleEditorRee,
      source: { ...exampleEditorRee.source, sourceAvailable: false },
    };
    expect(authoringStepStatuses(steps, withoutSource, {})).toEqual({
      source: "ready",
      build: "blocked",
      crosscheck: "blocked",
    });

    expect(authoringStepStatuses(steps, exampleEditorRee, { build: true })).toEqual({
      source: "complete",
      build: "complete",
      crosscheck: "ready",
    });
  });

  it("routes the cross-check to its SBOM authoring surface", () => {
    expect(authoringPageForStep("crosscheck")).toBe(PAGE.SBOM);
    expect(authoringPageForStep("unknown")).toBeUndefined();
  });
});
