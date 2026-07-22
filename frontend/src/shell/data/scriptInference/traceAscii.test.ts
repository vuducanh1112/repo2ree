import type { DecisionDag, DecisionTrace } from "@shell/infra/api/apiTypes";
import { describe, expect, it } from "vitest";
import { renderDecisionDiagram, renderDecisionTrace } from "./traceAscii";

// Minimal trace shapes mirroring the backend's build-inference output; cast
// through unknown so the fixtures aren't coupled to the full generated type.
function trace(over: Partial<Record<string, unknown>>): DecisionTrace {
  return {
    dag: "build-inference",
    version: 1,
    steps: [],
    edges: [],
    result_node: "",
    ...over,
  } as unknown as DecisionTrace;
}

const DECISION = trace({
  steps: [
    {
      node_id: "project-root",
      kind: "check",
      check: "logical_project_root",
      branch: "root",
      observed: { kind: "logical_root", path: ".", wrapper_depth: 0 },
    },
    { node_id: "runtime-strategies", kind: "fork", outcome: "evaluated: 2" },
    {
      node_id: "dockerfiles-at-root",
      kind: "check",
      check: "dockerfiles_at_project_root",
      branch: "exactly_one",
      observed: { kind: "path_matches", count: 1, paths: ["Dockerfile"] },
    },
    { node_id: "dockerfile-complete", kind: "strategy_leaf", outcome: "complete" },
    {
      node_id: "requirements-at-root",
      kind: "check",
      check: "requirements_at_project_root",
      branch: "exactly_one",
      observed: { kind: "path_matches", count: 1, paths: ["requirements.txt"] },
    },
    { node_id: "pip-candidate", kind: "strategy_leaf", outcome: "candidate" },
    {
      node_id: "resolve-runtime-strategies",
      kind: "resolve",
      outcome: "needs_input",
      observed: {
        kind: "strategy_outcomes",
        outcomes: [
          { strategy: "dockerfile", outcome: "complete", leaf: "dockerfile-complete" },
          { strategy: "pip", outcome: "candidate", leaf: "pip-candidate" },
        ],
      },
    },
    { node_id: "build-needs-input", kind: "result", outcome: "needs_input" },
  ],
  edges: [
    { source: "runtime-strategies", branch: "dockerfile", target: "dockerfiles-at-root" },
    { source: "runtime-strategies", branch: "pip", target: "requirements-at-root" },
  ],
  result_node: "build-needs-input",
});

describe("renderDecisionTrace", () => {
  it("renders the header, prefix, forked branches, resolver, and result", () => {
    const text = renderDecisionTrace(DECISION);
    expect(text).toContain("build-inference (v1)");
    expect(text).toContain("logical_project_root -> root");
    expect(text).toContain('logical root "." (depth 0)');
    expect(text).toContain("fork: runtime-strategies");
    // One indented group per forked strategy, labelled by the fork edge.
    expect(text).toContain("|-- dockerfile");
    expect(text).toContain("|-- pip");
    // Outcome glyphs from the design legend.
    expect(text).toContain("[*] dockerfile-complete (complete)");
    expect(text).toContain("[!] pip-candidate (candidate)");
    // Resolver join carries the per-strategy outcomes, then the result node.
    expect(text).toContain("resolve: resolve-runtime-strategies -> needs_input");
    expect(text).toContain("dockerfile=complete, pip=candidate");
    expect(text).toContain("=> build-needs-input (needs_input)");
  });

  it("groups each branch's checks under its strategy", () => {
    const text = renderDecisionTrace(DECISION);
    const lines = text.split("\n");
    const pipIdx = lines.findIndex((l) => l.includes("|-- pip"));
    // The requirements check belongs to the pip branch, after its label.
    const reqIdx = lines.findIndex((l) => l.includes("requirements_at_project_root"));
    expect(pipIdx).toBeGreaterThanOrEqual(0);
    expect(reqIdx).toBeGreaterThan(pipIdx);
  });

  it("renders a not-inferred decline with not_applicable leaves", () => {
    const declined = trace({
      steps: [
        {
          node_id: "project-root",
          kind: "check",
          check: "logical_project_root",
          branch: "root",
          observed: { kind: "logical_root", path: ".", wrapper_depth: 0 },
        },
        { node_id: "runtime-strategies", kind: "fork", outcome: "evaluated: 2" },
        {
          node_id: "dockerfiles-at-root",
          kind: "check",
          check: "dockerfiles_at_project_root",
          branch: "none",
          observed: { kind: "path_matches", count: 0, paths: [] },
        },
        {
          node_id: "nested-dockerfiles",
          kind: "check",
          check: "nested_dockerfiles",
          branch: "none",
          observed: { kind: "path_matches", count: 0, paths: [] },
        },
        { node_id: "dockerfile-not-applicable", kind: "strategy_leaf", outcome: "not_applicable" },
        {
          node_id: "requirements-at-root",
          kind: "check",
          check: "requirements_at_project_root",
          branch: "none",
          observed: { kind: "path_matches", count: 0, paths: [] },
        },
        { node_id: "pip-not-applicable", kind: "strategy_leaf", outcome: "not_applicable" },
        {
          node_id: "resolve-runtime-strategies",
          kind: "resolve",
          outcome: "not_inferred",
          observed: { kind: "strategy_outcomes", outcomes: [] },
        },
        { node_id: "build-not-inferred", kind: "result", outcome: "not_inferred" },
      ],
      edges: [
        { source: "runtime-strategies", branch: "dockerfile", target: "dockerfiles-at-root" },
        { source: "runtime-strategies", branch: "pip", target: "requirements-at-root" },
      ],
      result_node: "build-not-inferred",
    });
    const text = renderDecisionTrace(declined);
    expect(text).toContain("[o] dockerfile-not-applicable (not_applicable)");
    expect(text).toContain("[o] pip-not-applicable (not_applicable)");
    expect(text).toContain("=> build-not-inferred (not_inferred)");
  });

  it("degrades to a placeholder for an empty trace", () => {
    expect(renderDecisionTrace(trace({ steps: [] }))).toBe("(no decision trace)");
  });
});

// A trimmed static DAG mirroring build-inference: a check, a fork, one check per
// branch, two leaves, a resolver, and two result nodes.
function dag(): DecisionDag {
  return {
    key: "build-inference",
    version: 1,
    root: "project-root",
    nodes: [
      {
        id: "project-root",
        kind: "check",
        check: "logical_project_root",
        branches: { root: "fork", wrapper: "fork" },
      },
      {
        id: "fork",
        kind: "fork",
        branches: { dockerfile: "df-check", pip: "pip-check" },
        join: "resolve",
      },
      {
        id: "df-check",
        kind: "check",
        check: "dockerfiles_at_project_root",
        branches: { none: "df-na", exactly_one: "df-complete" },
      },
      {
        id: "df-complete",
        kind: "strategy_leaf",
        strategy: "dockerfile",
        outcome: "complete",
        rule: "r-df",
        next: "resolve",
      },
      {
        id: "df-na",
        kind: "strategy_leaf",
        strategy: "dockerfile",
        outcome: "not_applicable",
        next: "resolve",
      },
      {
        id: "pip-check",
        kind: "check",
        check: "requirements_at_project_root",
        branches: { none: "pip-na", exactly_one: "pip-cand" },
      },
      {
        id: "pip-cand",
        kind: "strategy_leaf",
        strategy: "pip",
        outcome: "candidate",
        rule: "r-pip",
        next: "resolve",
      },
      {
        id: "pip-na",
        kind: "strategy_leaf",
        strategy: "pip",
        outcome: "not_applicable",
        next: "resolve",
      },
      {
        id: "resolve",
        kind: "resolve",
        fork: "fork",
        resolver: "score_free_viability_v1",
        branches: { complete: "r-complete", needs_input: "r-needs", not_inferred: "r-none" },
      },
      { id: "r-complete", kind: "result", status: "complete", application: "automatic_allowed" },
      {
        id: "r-needs",
        kind: "result",
        status: "needs_input",
        application: "confirmation_required",
      },
      { id: "r-none", kind: "result", status: "not_inferred", application: "unavailable" },
    ],
  } as unknown as DecisionDag;
}

// A trace that took root -> fork -> (dockerfile none -> df-na) & (pip exactly_one
// -> pip-cand) -> resolve needs_input -> r-needs.
const OVERLAY_TRACE = trace({
  steps: [
    {
      node_id: "project-root",
      kind: "check",
      branch: "root",
      observed: { kind: "logical_root", path: ".", wrapper_depth: 0 },
    },
    { node_id: "fork", kind: "fork" },
    {
      node_id: "df-check",
      kind: "check",
      branch: "none",
      observed: { kind: "path_matches", count: 0, paths: [] },
    },
    { node_id: "df-na", kind: "strategy_leaf", outcome: "not_applicable" },
    {
      node_id: "pip-check",
      kind: "check",
      branch: "exactly_one",
      observed: { kind: "path_matches", count: 1, paths: ["requirements.txt"] },
    },
    { node_id: "pip-cand", kind: "strategy_leaf", outcome: "candidate" },
    { node_id: "resolve", kind: "resolve", outcome: "needs_input" },
    { node_id: "r-needs", kind: "result", outcome: "needs_input" },
  ],
  edges: [
    { source: "project-root", branch: "root", target: "fork" },
    { source: "fork", branch: "dockerfile", target: "df-check" },
    { source: "fork", branch: "pip", target: "pip-check" },
    { source: "df-check", branch: "none", target: "df-na" },
    { source: "pip-check", branch: "exactly_one", target: "pip-cand" },
    { source: "resolve", branch: "needs_input", target: "r-needs" },
  ],
  result_node: "r-needs",
});

describe("renderDecisionDiagram", () => {
  it("shows every node, marking evaluated vs not", () => {
    const text = renderDecisionDiagram(dag(), OVERLAY_TRACE);
    // Header + legend.
    expect(text).toContain("build-inference (v1)");
    expect(text).toContain("[>] evaluated");
    // Evaluated nodes on the path.
    expect(text).toContain("[>] project-root");
    expect(text).toContain("[>] pip-cand");
    // Unevaluated nodes still rendered (muted marker), not dropped.
    expect(text).toContain("[ ] df-complete");
    expect(text).toContain("[ ] r-complete");
    expect(text).toContain("[ ] r-none");
  });

  it("flags the branch taken out of each visited node", () => {
    const text = renderDecisionDiagram(dag(), OVERLAY_TRACE);
    // Whitespace-tolerant: branch lines are column-padded for alignment.
    const norm = (s: string) => s.replace(/\s+/g, " ").trim();
    const line = (needle: string) =>
      text
        .split("\n")
        .map(norm)
        .find((l) => l.includes(norm(needle))) ?? "";
    // Taken branches carry the marker; sibling branches do not.
    expect(line("root -> fork")).toContain("<=");
    expect(line("exactly_one -> pip-cand")).toContain("<=");
    expect(line("needs_input -> r-needs")).toContain("<=");
    expect(line("complete -> r-complete")).not.toContain("<=");
    expect(line("none -> df-na")).toContain("<=");
    expect(line("exactly_one -> df-complete")).not.toContain("<=");
  });

  it("renders leaf outcomes, resolver, and result headers", () => {
    const text = renderDecisionDiagram(dag(), OVERLAY_TRACE);
    expect(text).toContain("leaf [!] candidate  rule r-pip");
    expect(text).toContain("resolve: score_free_viability_v1");
    expect(text).toContain("result: needs_input / confirmation_required");
  });
});
