import type { InferenceReport } from "@shell/infra/api/apiTypes";
import { describe, expect, it } from "vitest";
import { selectRunCandidate, selectRunDag, selectRunTrace } from "./runCandidate";

// A minimally-shaped report: only the fields the selectors read. Cast through
// unknown so the test isn't coupled to the full generated wire type.
function report(results: unknown[], dags: unknown[] = []): InferenceReport {
  return { results, dags } as unknown as InferenceReport;
}

function candidate(overrides: Record<string, unknown> = {}): unknown {
  return {
    body: "#!/usr/bin/env sh\nset --\n",
    inference_rule: "docker-runtime-activation-v1",
    application: "confirmation_required",
    ...overrides,
  };
}

describe("selectRunCandidate", () => {
  it("returns the activation target's first candidate", () => {
    const result = selectRunCandidate(
      report([{ target: { kind: "activation_run" }, candidates: [candidate()], warnings: [] }]),
      "activation_run",
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.ruleId).toBe("docker-runtime-activation-v1");
    expect(result.script.application).toBe("confirmation_required");
  });

  it("surfaces blocking warning messages when not inferred", () => {
    const result = selectRunCandidate(
      report([
        {
          target: { kind: "activation_run" },
          candidates: [],
          warnings: [
            {
              code: "runtime_artifact_missing",
              blocking: true,
              message: "Build the runtime first.",
            },
            { code: "execution_not_validated", blocking: false, message: "info" },
          ],
        },
      ]),
      "activation_run",
    );
    expect(result.status).toBe("not_inferred");
    if (result.status !== "not_inferred") return;
    expect(result.blockingMessages).toEqual(["Build the runtime first."]);
  });

  it("matches an experiment target by name", () => {
    const rep = report([
      {
        target: { kind: "experiment_run", experiment_name: "a" },
        candidates: [candidate()],
        warnings: [],
      },
      { target: { kind: "experiment_run", experiment_name: "b" }, candidates: [], warnings: [] },
    ]);
    expect(selectRunCandidate(rep, "experiment_run", "a").status).toBe("generated");
    expect(selectRunCandidate(rep, "experiment_run", "b").status).toBe("not_inferred");
  });

  it("reports the alternative count when several runtimes were viable", () => {
    const result = selectRunCandidate(
      report([
        {
          target: { kind: "activation_run" },
          candidates: [candidate(), candidate({ inference_rule: "venv-runtime-activation-v1" })],
          warnings: [],
        },
      ]),
      "activation_run",
    );
    if (result.status !== "generated") throw new Error("expected generated");
    expect(result.script.alternativeCount).toBe(2);
  });
});

describe("selectRunTrace / selectRunDag", () => {
  it("returns the trace and the matching static DAG for the target", () => {
    const rep = report(
      [
        {
          target: { kind: "activation_run" },
          candidates: [],
          warnings: [],
          decision: { dag: "activation-run-inference" },
        },
      ],
      [{ key: "activation-run-inference" }, { key: "build-inference" }],
    );
    expect(selectRunTrace(rep, "activation_run")?.dag).toBe("activation-run-inference");
    expect(selectRunDag(rep, "activation_run")?.key).toBe("activation-run-inference");
  });
});
