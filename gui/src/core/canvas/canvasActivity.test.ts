import { PAGE } from "@core/app-shell/pages";
import { canvasActivity } from "@core/canvas/canvasActivity";
import type { ReeRunOperation } from "@core/generated/vocabulary";
import type { ReeRunSummary } from "@core/runs/ReeRun";
import type { ReeRunStatus } from "@core/runs/ReeRunStatus";
import { describe, expect, it } from "vitest";

function run(operation: ReeRunOperation, status: ReeRunStatus): ReeRunSummary {
  return { runId: `${operation}-${status}`, operation, status, createdAt: "2026-01-01T00:00:00Z" };
}

describe("canvasActivity", () => {
  it("is empty when nothing is in flight", () => {
    const activity = canvasActivity([
      run("build_experiment_environment", "succeeded"),
      run("run_experiment", "failed"),
    ]);
    expect(activity.nodeKeys.size).toBe(0);
    expect(activity.zones.size).toBe(0);
  });

  it("lights the build panel and the inner shell while the experiment environment builds", () => {
    const activity = canvasActivity([run("build_experiment_environment", "running")]);
    expect([...activity.nodeKeys]).toEqual([PAGE.BUILD_EXPERIMENT_ENVIRONMENT]);
    expect([...activity.zones]).toEqual(["inner"]);
  });

  it("lights the core while an experiment runs", () => {
    const activity = canvasActivity([run("run_experiment", "queued")]);
    expect([...activity.nodeKeys]).toEqual([PAGE.EXPERIMENTS]);
    expect([...activity.zones]).toEqual(["core"]);
  });

  it("reads the cross-check as the SBOM panel", () => {
    expect([...canvasActivity([run("cross_check_sbom", "running")]).nodeKeys]).toEqual([
      PAGE.GENERATE_SBOM,
    ]);
  });

  it("ignores operations that raise the lab rather than a panel", () => {
    const activity = canvasActivity([
      run("initialize_ree", "running"),
      run("load_ree_bundle", "running"),
    ]);
    expect(activity.nodeKeys.size).toBe(0);
  });

  it("carries client-driven work that has no run of its own", () => {
    const activity = canvasActivity([], [PAGE.SEAL_REE]);
    expect([...activity.nodeKeys]).toEqual([PAGE.SEAL_REE]);
    expect([...activity.zones]).toEqual(["outer"]);
  });

  it("reports every shell that has work in it", () => {
    const activity = canvasActivity([
      run("build_experiment_environment", "running"),
      run("run_experiment", "running"),
      run("acquire_source", "running"),
    ]);
    expect([...activity.zones].sort()).toEqual(["core", "inner", "outer"]);
  });
});
