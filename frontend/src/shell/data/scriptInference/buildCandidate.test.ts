import type { InferenceReport } from "@shell/infra/api/apiTypes";
import { describe, expect, it } from "vitest";
import { selectBuildCandidate } from "./buildCandidate";

// A minimally-shaped report: only the fields selectBuildCandidate reads. Cast
// through unknown so the test isn't coupled to the full generated wire type.
function report(results: unknown[]): InferenceReport {
  return { results } as unknown as InferenceReport;
}

function candidate(overrides: Record<string, unknown> = {}): unknown {
  return {
    body: "#!/usr/bin/env sh\n",
    inference_rule: "single-project-root-dockerfile-v1",
    application: "automatic_allowed",
    ...overrides,
  };
}

describe("selectBuildCandidate", () => {
  it("returns the build target's first candidate as a generated script", () => {
    const result = selectBuildCandidate(
      report([{ target: { kind: "build" }, candidates: [candidate()] }]),
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.body).toContain("#!/usr/bin/env sh");
    expect(result.script.ruleId).toBe("single-project-root-dockerfile-v1");
    expect(result.script.application).toBe("automatic_allowed");
    expect(result.script.alternativeCount).toBe(1);
  });

  it("reports not_inferred when the build target has no candidates", () => {
    const result = selectBuildCandidate(report([{ target: { kind: "build" }, candidates: [] }]));
    expect(result.status).toBe("not_inferred");
  });

  it("reports not_inferred when there is no build target", () => {
    const result = selectBuildCandidate(
      report([{ target: { kind: "activation_run" }, candidates: [candidate()] }]),
    );
    expect(result.status).toBe("not_inferred");
  });

  it("surfaces the confirmation policy for a generated strategy", () => {
    const result = selectBuildCandidate(
      report([
        {
          target: { kind: "build" },
          candidates: [
            candidate({
              inference_rule: "root-pip-requirements-v1",
              application: "confirmation_required",
            }),
          ],
        },
      ]),
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    expect(result.script.application).toBe("confirmation_required");
    expect(result.script.ruleId).toBe("root-pip-requirements-v1");
  });

  it("surfaces the alternative count when several strategies are viable", () => {
    const result = selectBuildCandidate(
      report([
        {
          target: { kind: "build" },
          candidates: [
            candidate({ inference_rule: "single-project-root-dockerfile-v1" }),
            candidate({ inference_rule: "root-pip-requirements-v1" }),
          ],
        },
      ]),
    );
    expect(result.status).toBe("generated");
    if (result.status !== "generated") return;
    // The first candidate is loaded; the count tells the author others exist.
    expect(result.script.ruleId).toBe("single-project-root-dockerfile-v1");
    expect(result.script.alternativeCount).toBe(2);
  });

  it("skips a candidate with an empty body", () => {
    const result = selectBuildCandidate(
      report([{ target: { kind: "build" }, candidates: [candidate({ body: "" })] }]),
    );
    expect(result.status).toBe("not_inferred");
  });
});
