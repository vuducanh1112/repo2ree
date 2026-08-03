import { describe, expect, it } from "vitest";
import { formatReceiptDuration, parseAuthorReceipts } from "./authorReceipts";

function receipt(operation: string, fields: Record<string, unknown> = {}) {
  return {
    schema_version: 1,
    operation,
    run_id: `run-${operation}`,
    started_at: "2026-07-24T10:00:00Z",
    finished_at: "2026-07-24T10:00:01Z",
    duration_ms: 1200,
    recorded_at: "2026-07-24T10:00:01Z",
    ...fields,
  };
}

describe("formatReceiptDuration", () => {
  it("renders the same shape as the backend log", () => {
    expect(formatReceiptDuration(820)).toBe("820ms");
    expect(formatReceiptDuration(12_400)).toBe("12.400s");
    expect(formatReceiptDuration(187_000)).toBe("3m 7s");
    expect(formatReceiptDuration(3_723_000)).toBe("1h 2m 3s");
    expect(formatReceiptDuration(-5)).toBe("0ms");
  });
});

describe("parseAuthorReceipts", () => {
  it("flattens inline receipts in pipeline order", () => {
    const views = parseAuthorReceipts({
      source: receipt("acquire_source"),
      build: receipt("build_runtime"),
      experiments: {
        "figure-2": receipt("run_experiment", { experiment_name: "figure-2" }),
        "figure-1": receipt("run_experiment", { experiment_name: "figure-1" }),
      },
    });

    expect(views.map((view) => view.title)).toEqual([
      "Source acquired",
      "Runtime built",
      "Experiment run · figure-1",
      "Experiment run · figure-2",
    ]);
    expect(views[0].duration).toBe("1.200s");
  });

  it("keeps operation payload fields and abbreviates digests", () => {
    const [view] = parseAuthorReceipts({
      build: receipt("build_runtime", {
        build_runtime_script_path: "scripts/build.sh",
        produced_runtime_digest: "sha256:0123456789abcdef0123456789abcdef",
        workspace_drift: { status: "modified", changed_path_count: 3 },
      }),
    });

    expect(view.fields.map((field) => field.key)).toEqual([
      "build_runtime_script_path",
      "produced_runtime_digest",
      "workspace_drift",
    ]);
    expect(view.fields[1].value).toBe("sha256:012345678…");
    expect(view.fields[2].value).toBe("modified (3 paths)");
  });

  it("drops absent or unusable receipt slots", () => {
    expect(parseAuthorReceipts(undefined)).toEqual([]);
    expect(parseAuthorReceipts({ source: {}, experiments: { bad: { run_id: "x" } } })).toEqual([]);
  });
});
