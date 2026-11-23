import type { DecisionDag, DecisionStep, DecisionTrace } from "@shell/infra/api/apiTypes";

type DagNode = DecisionDag["nodes"][number];

const OUTCOME_GLYPH: Record<string, string> = {
  complete: "[*]",
  candidate: "[!]",
  blocked: "[x]",
  not_applicable: "[o]",
};

export function renderDecisionTrace(trace: DecisionTrace): string {
  if (!trace.steps || trace.steps.length === 0) return "(no decision trace)";

  const lines: string[] = [`${trace.dag} (v${trace.version})`, ""];
  const forkIndex = trace.steps.findIndex((step) => step.kind === "fork");
  const resolveIndex = trace.steps.findIndex((step) => step.kind === "resolve");

  if (forkIndex === -1 || resolveIndex === -1 || resolveIndex < forkIndex) {
    for (const step of trace.steps) lines.push(...renderStep(step, ""));
    return lines.join("\n");
  }

  for (const step of trace.steps.slice(0, forkIndex)) lines.push(...renderStep(step, ""));

  const fork = trace.steps[forkIndex];
  lines.push(`+ fork: ${fork.node_id}`);

  const strategyOf = new Map<string, string>();
  for (const edge of trace.edges) {
    if (edge.source === fork.node_id) strategyOf.set(edge.target, edge.branch);
  }

  const branchSteps = trace.steps.slice(forkIndex + 1, resolveIndex);
  for (const group of groupBranches(branchSteps)) {
    const strategy = strategyOf.get(group[0]?.node_id ?? "") ?? "?";
    lines.push(`|-- ${strategy}`);
    for (const step of group) {
      for (const line of renderStep(step, "|     ")) lines.push(line);
    }
  }

  const resolve = trace.steps[resolveIndex];
  lines.push(`\`-- resolve: ${resolve.node_id} -> ${resolve.outcome ?? "?"}`);
  const detail = observedDetail(resolve);
  if (detail) lines.push(`      ${detail}`);
  for (const step of trace.steps.slice(resolveIndex + 1)) {
    lines.push(`=> ${step.node_id} (${step.outcome ?? "?"})`);
  }
  return lines.join("\n");
}

function groupBranches(steps: DecisionStep[]): DecisionStep[][] {
  const groups: DecisionStep[][] = [];
  let current: DecisionStep[] = [];
  for (const step of steps) {
    current.push(step);
    if (step.kind === "strategy_leaf") {
      groups.push(current);
      current = [];
    }
  }
  if (current.length > 0) groups.push(current);
  return groups;
}

function renderStep(step: DecisionStep, indent: string): string[] {
  const lines: string[] = [];
  if (step.kind === "check") {
    lines.push(`${indent}${step.check ?? step.node_id} -> ${step.branch ?? "?"}`);
  } else if (step.kind === "strategy_leaf") {
    const glyph = OUTCOME_GLYPH[step.outcome ?? ""] ?? "[-]";
    lines.push(`${indent}${glyph} ${step.node_id} (${step.outcome ?? "?"})`);
  } else if (step.kind === "result") {
    lines.push(`=> ${step.node_id} (${step.outcome ?? "?"})`);
  } else {
    lines.push(`${indent}${step.kind}: ${step.node_id}`);
  }
  const detail = observedDetail(step);
  if (detail && step.kind !== "strategy_leaf") lines.push(`${indent}    ${detail}`);
  return lines;
}

export function renderDecisionDiagram(dag: DecisionDag, trace: DecisionTrace): string {
  const visited = new Set(trace.steps.map((step) => step.node_id));
  const stepByNode = new Map(trace.steps.map((step) => [step.node_id, step]));
  const takenEdge = new Set(
    trace.edges.map((edge) => `${edge.source}|${edge.branch}|${edge.target}`),
  );

  const lines: string[] = [
    `${dag.key} (v${dag.version})`,
    "legend: [>] evaluated   [ ] not evaluated   <= branch taken",
    "",
  ];

  for (const node of dag.nodes) {
    const mark = visited.has(node.id) ? "[>]" : "[ ]";
    lines.push(`${mark} ${node.id}   ${nodeHeader(node)}`);

    const step = stepByNode.get(node.id);
    if (step) {
      const detail = observedDetail(step);
      if (detail) lines.push(`        ${detail}`);
    }

    const branches = outgoingBranches(node);
    const width = Math.max(0, ...branches.map(([key]) => key.length));
    for (const [key, target] of branches) {
      const taken = takenEdge.has(`${node.id}|${key}|${target}`) ? "  <=" : "";
      lines.push(`        ${key.padEnd(width)} -> ${target}${taken}`);
    }
  }
  return lines.join("\n");
}

function nodeHeader(node: DagNode): string {
  switch (node.kind) {
    case "check":
      return `check: ${node.check}`;
    case "fork":
      return `fork (join ${node.join})`;
    case "strategy_leaf": {
      const glyph = OUTCOME_GLYPH[node.outcome] ?? "[-]";
      const rule = node.rule ? `  rule ${node.rule}` : "";
      return `leaf ${glyph} ${node.outcome}${rule}`;
    }
    case "resolve":
      return `resolve: ${node.resolver}`;
    case "result":
      return `result: ${node.status} / ${node.application}`;
  }
}

function outgoingBranches(node: DagNode): [string, string][] {
  switch (node.kind) {
    case "check":
    case "resolve":
      return Object.entries(node.branches);
    case "fork":
      return Object.entries(node.branches);
    case "strategy_leaf":
      return [["join", node.next]];
    case "result":
      return [];
  }
}

function observedDetail(step: DecisionStep): string {
  const observed = step.observed;
  if (!observed) return "";
  if (observed.kind === "logical_root") {
    return `logical root "${observed.path}" (depth ${observed.wrapper_depth})`;
  }
  if (observed.kind === "path_matches") {
    if (observed.count === 0) return "0 matches";
    return `${observed.count} match${observed.count > 1 ? "es" : ""}: ${observed.paths.join(", ")}`;
  }
  if (observed.kind === "strategy_outcomes") {
    return observed.outcomes.map((outcome) => `${outcome.strategy}=${outcome.outcome}`).join(", ");
  }
  return "";
}
