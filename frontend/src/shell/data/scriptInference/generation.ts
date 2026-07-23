// The one shape a generated script takes, whatever target produced it. Build and
// the run scaffolds (activation / experiment) differ only in how they are
// inferred, not in what the editor and the generate control need back, so one
// selector returns this and one control renders it.

export type ScriptApplication = "automatic_allowed" | "confirmation_required" | "unavailable";

export interface GeneratedScript {
  // The rendered script body to load into the editor.
  body: string;
  // The rule that produced it (e.g. "single-project-root-dockerfile-v1").
  ruleId: string;
  // Advisory: whether a human should confirm before saving. Inference never
  // writes, so this is advice, not a gate.
  application: ScriptApplication;
  // How many candidates the target returned (>1 means several viable runtimes /
  // strategies — a decision, not a default).
  alternativeCount: number;
  // Blocking warning messages the author must resolve before the script is
  // usable, e.g. two Dockerfiles at the project root or an unbuilt runtime.
  blockingMessages: string[];
}

export type ScriptGeneration =
  | { status: "generated"; script: GeneratedScript }
  // Nothing could be inferred (no clear evidence, undeclared experiment,
  // unresolved runtime, …). The trace explains why; any blocking warnings that
  // were raised regardless ride along here.
  | { status: "not_inferred"; blockingMessages: string[] };
