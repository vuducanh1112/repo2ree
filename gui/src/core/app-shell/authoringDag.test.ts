import { describe, expect, it } from "vitest";
import { exampleEditorRee } from "../../../tests/support/stepPageFixture";
import {
  type AuthoringStep,
  authoringPageForStep,
  authoringStepStatuses,
  nextAuthoringStep,
} from "./authoringDag";
import { PAGE } from "./pages";

const steps: AuthoringStep[] = [
  { key: "source", order: 1, label: "Source", requires: [], actions: [] },
  { key: "build", order: 2, label: "Build", requires: ["source"], actions: [] },
  { key: "crosscheck", order: 3, label: "Cross-check", requires: ["build"], actions: [] },
];

describe("authoring DAG", () => {
  it("derives readiness from catalog edges and current REE evidence", () => {
    // A REE that has run nothing yet: no source in the workspace, and no
    // receipt on the aggregate for anything downstream of it.
    const withoutSource = {
      ...exampleEditorRee,
      source: { ...exampleEditorRee.source, sourceAvailable: false },
      audit: {},
    };
    expect(authoringStepStatuses(steps, withoutSource, {})).toEqual({
      source: "ready",
      build: "blocked",
      crosscheck: "blocked",
    });

    // No badges: completion is the REE's own audit, so a reloaded tab reads the
    // same statuses a mid-session one does.
    expect(authoringStepStatuses(steps, exampleEditorRee, {})).toEqual({
      source: "complete",
      build: "complete",
      crosscheck: "ready",
    });
  });

  it("names the lowest-order ready step, whatever order the catalog arrives in", () => {
    // Two branches open at once: build (2) and a parallel step ordered after it.
    const branched: AuthoringStep[] = [
      { key: "crosscheck", order: 3, label: "Cross-check", requires: ["source"], actions: [] },
      { key: "build", order: 2, label: "Build", requires: ["source"], actions: [] },
      { key: "source", order: 1, label: "Source", requires: [], actions: [] },
    ];
    const statuses = authoringStepStatuses(
      branched,
      { ...exampleEditorRee, audit: { source: "current" as const } },
      {},
    );
    expect(statuses).toMatchObject({ build: "ready", crosscheck: "ready" });
    expect(nextAuthoringStep(branched, statuses)?.key).toBe("build");

    // Nothing ready — everything is either done or waiting on a requirement.
    expect(
      nextAuthoringStep(steps, { source: "complete", build: "blocked", crosscheck: "blocked" }),
    ).toBeUndefined();
  });

  it("routes the cross-check to its SBOM authoring surface", () => {
    expect(authoringPageForStep("crosscheck")).toBe(PAGE.SBOM);
    expect(authoringPageForStep("unknown")).toBeUndefined();
  });
});
