import { UnknownWireNames } from "@core/contract/unknownNames";
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
      acquire_source: receipt("acquire_source"),
      build_experiment_environment: receipt("build_experiment_environment"),
      experiments: {
        "figure-2": receipt("run_experiment", { experiment_name: "figure-2" }),
        "figure-1": receipt("run_experiment", { experiment_name: "figure-1" }),
      },
    });

    expect(views.map((view) => view.title)).toEqual([
      "Source acquired",
      "Experiment environment built",
      "Experiment run · figure-1",
      "Experiment run · figure-2",
    ]);
    expect(views[0].duration).toBe("1.200s");
  });

  it("keeps operation payload fields and abbreviates digests", () => {
    const [view] = parseAuthorReceipts({
      build_experiment_environment: receipt("build_experiment_environment", {
        build_experiment_environment_script_path: "scripts/build.sh",
        produced_artifact_digest: "sha256:0123456789abcdef0123456789abcdef",
      }),
    });

    expect(view.fields.map((field) => field.key)).toEqual([
      "build_experiment_environment_script_path",
      "produced_artifact_digest",
    ]);
    expect(view.fields[1].value).toBe("sha256:012345678…");
  });

  it("drops absent or unusable receipt slots", () => {
    expect(parseAuthorReceipts(undefined)).toEqual([]);
    expect(
      parseAuthorReceipts({ acquire_source: null, experiments: { bad: { run_id: "x" } } }),
    ).toEqual([]);
  });

  it("refuses a slot or an operation the contract does not name", () => {
    expect(() => parseAuthorReceipts({ source: receipt("acquire_source") })).toThrow(
      UnknownWireNames,
    );
    expect(() => parseAuthorReceipts({ acquire_source: receipt("acquire") })).toThrow(/acquire/);
  });

  it("shows the working environment check in pipeline order", () => {
    const views = parseAuthorReceipts({
      build_experiment_environment: receipt("build_experiment_environment"),
      check_working_environment: receipt("check_working_environment"),
      acquire_source: receipt("acquire_source"),
    });
    expect(views.map((view) => view.title)).toEqual([
      "Source acquired",
      "Working environment checked",
      "Experiment environment built",
    ]);
  });

  it("uses the contract operation name for activation evidence", () => {
    const [view] = parseAuthorReceipts({
      activate_experiment_environment: receipt("activate_experiment_environment"),
    });
    expect(view.title).toBe("Activation tested");
  });
});
