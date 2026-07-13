import { describe, expect, it } from "vitest";
import type { ReeRunOperation, ReeRunSummary } from "./ReeRun";
import {
  activeRunCount,
  formatRunDuration,
  hudTabActivity,
  newestActiveRun,
  newestRun,
  RUN_HUD_TABS,
  runHudTabForOperation,
  runsForHudTab,
} from "./runHud";

function run(overrides: Partial<ReeRunSummary> & { runId: string }): ReeRunSummary {
  return {
    operation: "build",
    status: "succeeded",
    createdAt: "2026-01-01T10:00:00Z",
    ...overrides,
  };
}

const OPERATIONS: ReeRunOperation[] = [
  "provision",
  "source",
  "build",
  "sbom",
  "hbom",
  "activation",
  "evaluate",
  "swh",
  "zenodo",
  "dataverse",
  "experiment",
];

describe("runHudTabForOperation", () => {
  it("routes every operation to a tab", () => {
    const tabKeys = RUN_HUD_TABS.map((tab) => tab.key);
    for (const operation of OPERATIONS) {
      expect(tabKeys).toContain(runHudTabForOperation(operation));
    }
  });

  it("collects all archive repositories under the archive tab", () => {
    expect(runHudTabForOperation("swh")).toBe("archive");
    expect(runHudTabForOperation("zenodo")).toBe("archive");
    expect(runHudTabForOperation("dataverse")).toBe("archive");
  });
});

describe("runsForHudTab", () => {
  it("filters to the tab's operations and sorts newest first", () => {
    const runs = [
      run({ runId: "b-old", operation: "build", createdAt: "2026-01-01T09:00:00Z" }),
      run({ runId: "s-1", operation: "sbom", createdAt: "2026-01-01T09:30:00Z" }),
      run({ runId: "b-new", operation: "build", createdAt: "2026-01-01T11:00:00Z" }),
    ];
    expect(runsForHudTab(runs, "build").map((r) => r.runId)).toEqual(["b-new", "b-old"]);
    expect(runsForHudTab(runs, "sbom").map((r) => r.runId)).toEqual(["s-1"]);
    expect(runsForHudTab(runs, "evaluate")).toEqual([]);
  });
});

describe("activity selectors", () => {
  const runs = [
    run({ runId: "done", createdAt: "2026-01-01T09:00:00Z", status: "succeeded" }),
    run({ runId: "live", createdAt: "2026-01-01T10:00:00Z", status: "running" }),
    run({
      runId: "bad",
      operation: "sbom",
      createdAt: "2026-01-01T11:00:00Z",
      status: "failed",
    }),
  ];

  it("counts active runs", () => {
    expect(activeRunCount(runs)).toBe(1);
    expect(activeRunCount([])).toBe(0);
  });

  it("finds the newest active run across all statuses considered active", () => {
    expect(newestActiveRun(runs)?.runId).toBe("live");
    const provisioning = [run({ runId: "p", status: "provisioning" })];
    expect(newestActiveRun(provisioning)?.runId).toBe("p");
    expect(newestActiveRun([run({ runId: "x", status: "failed" })])).toBeUndefined();
  });

  it("picks the newest run overall for the ticker", () => {
    expect(newestRun(runs)?.runId).toBe("bad");
    expect(newestRun([])).toBeUndefined();
  });
});

describe("hudTabActivity", () => {
  it("lights the active flag while a tab run is in flight", () => {
    const runs = [run({ runId: "r", status: "running" })];
    expect(hudTabActivity(runs, "build")).toEqual({ active: true, failed: false });
  });

  it("flags a failure only when the tab's newest run failed or was canceled", () => {
    const failedThenFixed = [
      run({ runId: "old-fail", status: "failed", createdAt: "2026-01-01T09:00:00Z" }),
      run({ runId: "new-ok", status: "succeeded", createdAt: "2026-01-01T10:00:00Z" }),
    ];
    expect(hudTabActivity(failedThenFixed, "build").failed).toBe(false);

    const newestFailed = [run({ runId: "f", status: "failed" })];
    expect(hudTabActivity(newestFailed, "build").failed).toBe(true);

    const newestCanceled = [run({ runId: "c", status: "canceled" })];
    expect(hudTabActivity(newestCanceled, "build").failed).toBe(true);
  });

  it("suppresses the failure flag while a retry is running", () => {
    const retrying = [
      run({ runId: "f", status: "failed", createdAt: "2026-01-01T09:00:00Z" }),
      run({ runId: "retry", status: "running", createdAt: "2026-01-01T10:00:00Z" }),
    ];
    expect(hudTabActivity(retrying, "build")).toEqual({ active: true, failed: false });
  });
});

describe("formatRunDuration", () => {
  it("formats sub-minute and minute durations", () => {
    expect(
      formatRunDuration(
        run({
          runId: "r",
          startedAt: "2026-01-01T10:00:00Z",
          finishedAt: "2026-01-01T10:00:41Z",
        }),
      ),
    ).toBe("41s");
    expect(
      formatRunDuration(
        run({
          runId: "r",
          startedAt: "2026-01-01T10:00:00Z",
          finishedAt: "2026-01-01T10:04:02Z",
        }),
      ),
    ).toBe("4m 02s");
  });

  it("returns undefined for unfinished or unparsable windows", () => {
    expect(formatRunDuration(run({ runId: "r", status: "running" }))).toBeUndefined();
    expect(
      formatRunDuration(run({ runId: "r", startedAt: "garbage", finishedAt: "also-garbage" })),
    ).toBeUndefined();
  });
});
