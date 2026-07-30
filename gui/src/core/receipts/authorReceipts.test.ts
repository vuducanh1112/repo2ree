import { describe, expect, it } from "vitest";
import { formatReceiptDuration, parseAuthorReceipts } from "./authorReceipts";

function entry(receipt: Record<string, unknown>, consistency: Record<string, unknown> = {}) {
  return {
    key: `${receipt.operation}`,
    receipt: {
      schema_version: 1,
      run_id: "run-1",
      started_at: "2026-07-24T10:00:00Z",
      finished_at: "2026-07-24T10:00:01Z",
      duration_ms: 1200,
      recorded_at: "2026-07-24T10:00:01Z",
      status: "succeeded",
      ...receipt,
    },
    consistency: { step: `${receipt.operation}`, status: "fresh", ...consistency },
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
  it("orders receipts along the pipeline and labels each operation", () => {
    const views = parseAuthorReceipts({
      receipts: [
        entry({ operation: "run_experiment", experiment_name: "figure-2" }),
        entry({ operation: "build_runtime" }),
        entry({ operation: "acquire_source" }),
        entry({ operation: "run_experiment", experiment_name: "figure-1" }),
      ],
    });

    expect(views.map((view) => view.title)).toEqual([
      "Source acquired",
      "Runtime built",
      "Experiment run · figure-1",
      "Experiment run · figure-2",
    ]);
    expect(views[0].duration).toBe("1.200s");
  });

  it("keeps only the operation-specific payload as fields and abbreviates digests", () => {
    const [view] = parseAuthorReceipts({
      receipts: [
        entry({
          operation: "build_runtime",
          build_script_path: "scripts/build.sh",
          produced_runtime_digest: "sha256:0123456789abcdef0123456789abcdef",
          runtime_path: null,
          workspace_drift: { status: "modified", changed_path_count: 3 },
        }),
      ],
    });

    expect(view.fields.map((field) => field.key)).toEqual([
      "build_script_path",
      "produced_runtime_digest",
      "workspace_drift",
    ]);
    const digest = view.fields[1];
    expect(digest.value).toBe("sha256:012345678…");
    expect(digest.title).toBe("sha256:0123456789abcdef0123456789abcdef");
    expect(view.fields[2].value).toBe("modified (3 paths)");
  });

  it("carries the stale verdict with its recorded → current disagreement", () => {
    const [view] = parseAuthorReceipts({
      receipts: [
        entry(
          { operation: "generate_sbom" },
          {
            status: "stale",
            stale_inputs: [
              { input: "runtime", recorded: "sha256:aaa", current: "sha256:bbb" },
              { input: "", recorded: null, current: null },
            ],
          },
        ),
      ],
    });

    expect(view.freshness).toBe("stale");
    expect(view.staleInputs).toEqual([
      { input: "runtime", recorded: "sha256:aaa", current: "sha256:bbb" },
    ]);
  });

  it("drops unusable entries instead of blanking the console", () => {
    expect(parseAuthorReceipts(undefined)).toEqual([]);
    expect(parseAuthorReceipts({ receipts: [{}, { receipt: { run_id: "x" } }] })).toEqual([]);
  });

  it("sorts operations it does not know about last", () => {
    const views = parseAuthorReceipts({
      receipts: [entry({ operation: "review_replay" }), entry({ operation: "acquire_source" })],
    });

    expect(views.map((view) => view.operation)).toEqual(["acquire_source", "review_replay"]);
    expect(views[1].title).toBe("review_replay");
  });
});
