import { PAGE } from "@core/app-shell/pages";
import { canvasActivity } from "@core/canvas/canvasActivity";
import type { ReeRunOperation, ReeRunSummary } from "@core/runs/ReeRun";
import type { ReeRunStatus } from "@core/runs/ReeRunStatus";
import { describe, expect, it } from "vitest";

function run(operation: ReeRunOperation, status: ReeRunStatus): ReeRunSummary {
  return { runId: `${operation}-${status}`, operation, status, createdAt: "2026-01-01T00:00:00Z" };
}

describe("canvasActivity", () => {
  it("is empty when nothing is in flight", () => {
    const activity = canvasActivity([run("build", "succeeded"), run("experiment", "failed")]);
    expect(activity.nodeKeys.size).toBe(0);
    expect(activity.zones.size).toBe(0);
  });

  it("lights the build panel and the inner shell while the runtime builds", () => {
    const activity = canvasActivity([run("build", "running")]);
    expect([...activity.nodeKeys]).toEqual([PAGE.BUILD]);
    expect([...activity.zones]).toEqual(["inner"]);
  });

  it("lights the core while an experiment runs", () => {
    const activity = canvasActivity([run("experiment", "queued")]);
    expect([...activity.nodeKeys]).toEqual([PAGE.EXPERIMENTS]);
    expect([...activity.zones]).toEqual(["core"]);
  });

  it("collapses the three archive operations onto the one archive panel", () => {
    const activity = canvasActivity([run("zenodo", "running"), run("swh", "provisioning")]);
    expect([...activity.nodeKeys]).toEqual([PAGE.ARCHIVE]);
    expect([...activity.zones]).toEqual(["outer"]);
  });

  it("reads the cross-check as the SBOM panel", () => {
    expect([...canvasActivity([run("crosscheck", "running")]).nodeKeys]).toEqual([PAGE.SBOM]);
  });

  it("ignores operations that raise the lab rather than a panel", () => {
    const activity = canvasActivity([run("provision", "running"), run("ree-load", "running")]);
    expect(activity.nodeKeys.size).toBe(0);
  });

  it("carries client-driven work that has no run of its own", () => {
    const activity = canvasActivity([], [PAGE.SEAL]);
    expect([...activity.nodeKeys]).toEqual([PAGE.SEAL]);
    expect([...activity.zones]).toEqual(["outer"]);
  });

  it("reports every shell that has work in it", () => {
    const activity = canvasActivity([
      run("build", "running"),
      run("experiment", "running"),
      run("source", "running"),
    ]);
    expect([...activity.zones].sort()).toEqual(["core", "inner", "outer"]);
  });
});
