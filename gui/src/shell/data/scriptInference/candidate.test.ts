import type { InferenceReport } from "@shell/infra/api/apiTypes";
import { describe, expect, it } from "vitest";
import { selectCandidate, selectDag, selectTrace } from "./candidate";

// A minimally-shaped report: only the fields the selectors read. Cast through
// unknown so the test isn't coupled to the full generated wire type.
function report(results: unknown[], dags: unknown[] = []): InferenceReport {
  return { results, dags } as unknown as InferenceReport;
}

function candidate(overrides: Record<string, unknown> = {}): unknown {
  return {
    body: "#!/usr/bin/env sh\n",
    inference_rule: "single-project-root-dockerfile-v1",
    application: "automatic_allowed",
    ...overrides,
  };
}

describe("selectCandidate — build", () => {
  it("returns the build target's first candidate as a generated script", () => {
    const result = selectCandidate(
      report([{ target: { kind: "build_experiment_environment" }, candidates: [candidate()] }]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.body).toContain("#!/usr/bin/env sh");
    expect(result.script.ruleId).toBe("single-project-root-dockerfile-v1");
    expect(result.script.application).toBe("automatic_allowed");
    expect(result.script.alternativeCount).toBe(1);
  });

  it.each([
    [
      "reads the experiment environment path off the candidate's declaration dependency",
      "build/runtime.tar",
    ],
    ["leaves it undefined when the candidate records no experiment environment path", undefined],
  ] as const)("%s", (_name, path) => {
    const dependencies = path
      ? [
          {
            kind: "experiment_environment_declaration",
            path,
            digest: "",
            role: "experiment_environment",
          },
        ]
      : [{ kind: "source", path: "Dockerfile", digest: "sha256:x", role: "dockerfile" }];
    const result = selectCandidate(
      report([
        {
          target: { kind: "build_experiment_environment" },
          candidates: [candidate({ dependencies })],
        },
      ]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.experimentEnvironmentPath).toBe(path);
  });

  it("reports not_inferred when the build target has no candidates", () => {
    const result = selectCandidate(
      report([{ target: { kind: "build_experiment_environment" }, candidates: [] }]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("not_inferred");
  });

  it("reports not_inferred when there is no build target", () => {
    const result = selectCandidate(
      report([{ target: { kind: "activate_experiment_environment" }, candidates: [candidate()] }]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("not_inferred");
  });

  // The build DAG blocks on ambiguous evidence (two Dockerfiles at the project
  // root, an undeterminable build context, an undeclared runtime path) and says
  // so in a blocking warning. That message is the whole explanation, so it must
  // reach the author rather than being dropped on the way out of the report.
  it("surfaces the build target's blocking warnings", () => {
    const result = selectCandidate(
      report([
        {
          target: { kind: "build_experiment_environment" },
          candidates: [],
          warnings: [
            {
              code: "multiple_dockerfiles",
              blocking: true,
              message: "More than one Dockerfile sits at the logical project root.",
            },
            { code: "execution_not_validated", blocking: false, message: "info" },
          ],
        },
      ]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("not_inferred");
    if (result.status !== "not_inferred") return;
    expect(result.blockingMessages).toEqual([
      "More than one Dockerfile sits at the logical project root.",
    ]);
  });

  it("surfaces the confirmation policy for a generated strategy", () => {
    const result = selectCandidate(
      report([
        {
          target: { kind: "build_experiment_environment" },
          candidates: [
            candidate({
              inference_rule: "root-pip-requirements-v1",
              application: "confirmation_required",
            }),
          ],
        },
      ]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.application).toBe("confirmation_required");
    expect(result.script.ruleId).toBe("root-pip-requirements-v1");
  });

  it("surfaces the alternative count when several strategies are viable", () => {
    const result = selectCandidate(
      report([
        {
          target: { kind: "build_experiment_environment" },
          candidates: [
            candidate({ inference_rule: "single-project-root-dockerfile-v1" }),
            candidate({ inference_rule: "root-pip-requirements-v1" }),
          ],
        },
      ]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    // The first candidate is loaded; the count tells the author others exist.
    expect(result.script.ruleId).toBe("single-project-root-dockerfile-v1");
    expect(result.script.alternativeCount).toBe(2);
  });

  it("skips a candidate with an empty body", () => {
    const result = selectCandidate(
      report([
        { target: { kind: "build_experiment_environment" }, candidates: [candidate({ body: "" })] },
      ]),
      "build_experiment_environment",
    );
    expect(result.status).toBe("not_inferred");
  });
});

describe("selectCandidate — run scaffolds", () => {
  it("returns the activate target's first candidate", () => {
    const result = selectCandidate(
      report([
        {
          target: { kind: "activate_experiment_environment" },
          candidates: [
            candidate({
              inference_rule: "docker-activate-experiment-environment-v1",
              application: "confirmation_required",
            }),
          ],
          warnings: [],
        },
      ]),
      "activate_experiment_environment",
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.ruleId).toBe("docker-activate-experiment-environment-v1");
    expect(result.script.application).toBe("confirmation_required");
  });

  it("surfaces blocking warning messages when not inferred", () => {
    const result = selectCandidate(
      report([
        {
          target: { kind: "activate_experiment_environment" },
          candidates: [],
          warnings: [
            {
              code: "experiment_environment_artifact_missing",
              blocking: true,
              message: "Build the experiment environment first.",
            },
            { code: "execution_not_validated", blocking: false, message: "info" },
          ],
        },
      ]),
      "activate_experiment_environment",
    );
    expect(result.status).toBe("not_inferred");
    if (result.status !== "not_inferred") return;
    expect(result.blockingMessages).toEqual(["Build the experiment environment first."]);
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
    expect(selectCandidate(rep, "experiment_run", "a").status).toBe("generated");
    expect(selectCandidate(rep, "experiment_run", "b").status).toBe("not_inferred");
  });

  it("reports the alternative count when several runtimes were viable", () => {
    const result = selectCandidate(
      report([
        {
          target: { kind: "activate_experiment_environment" },
          candidates: [
            candidate(),
            candidate({ inference_rule: "venv-activate-experiment-environment-v1" }),
          ],
          warnings: [],
        },
      ]),
      "activate_experiment_environment",
    );
    if (result.status !== "generated") throw new Error("expected generated");
    expect(result.script.alternativeCount).toBe(2);
  });
});

describe("selectTrace / selectDag", () => {
  it("returns the trace and the matching static DAG for the target", () => {
    const rep = report(
      [
        {
          target: { kind: "activate_experiment_environment" },
          candidates: [],
          warnings: [],
          decision: { dag: "activate-experiment-environment-inference" },
        },
      ],
      [
        { key: "activate-experiment-environment-inference" },
        { key: "build-experiment-environment-inference" },
      ],
    );
    expect(selectTrace(rep, "activate_experiment_environment")?.dag).toBe(
      "activate-experiment-environment-inference",
    );
    expect(selectDag(rep, "activate_experiment_environment")?.key).toBe(
      "activate-experiment-environment-inference",
    );
  });
});
