// The exact commands a runtime substrate runs, projected by the backend from
// its EnvEntry (the same builders the executors use), so what is shown cannot
// drift from what runs. Run-scoped values appear as placeholder tokens
// documented in `placeholders`. Mirrors the backend CommandPlan.

export interface PlannedCommand {
  display: string;
  note: string;
}

export interface CommandPhase {
  id: "pre" | "exec" | "post";
  label: string;
  commands: PlannedCommand[];
}

export interface CommandPlan {
  kind: string;
  placeholders: Record<string, string>;
  phases: CommandPhase[];
  note: string;
}
