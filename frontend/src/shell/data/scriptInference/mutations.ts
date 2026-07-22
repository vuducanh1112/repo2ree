import type { DecisionDag, DecisionTrace } from "@shell/infra/api/apiTypes";
import { useMutation } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { selectBuildCandidate, selectBuildDag, selectBuildTrace } from "./buildCandidate";
import type { ScriptGeneration } from "./generation";
import {
  type RunTargetKind,
  selectRunCandidate,
  selectRunDag,
  selectRunTrace,
} from "./runCandidate";

// What every generate mutation resolves to: the script to load into the editor
// plus the executed decision-DAG walk (the explanation) and the full static
// graph it overlays onto. One shape so a single control renders any target.
export interface ScriptInferenceOutcome {
  generation: ScriptGeneration;
  // The executed decision-DAG walk for the target. Null only if the report has
  // no such target.
  trace: DecisionTrace | null;
  // The full static graph the trace overlays onto (all branches).
  dag: DecisionDag | null;
}

/**
 * Run read-only script inference for the build target and reduce it to the
 * script the build page loads into the editor plus its decision trace. The call
 * persists nothing — the returned body becomes a script only when the author
 * saves it — so there are no queries to invalidate on success.
 */
export function useGenerateBuildScript(reeId?: string) {
  const runtime = useApiRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation<ScriptInferenceOutcome>({
    mutationFn: async () => {
      const report = await runtime.reeApi.generateScriptCandidates(resolvedReeId, [
        { kind: "build" },
      ]);
      return {
        generation: selectBuildCandidate(report),
        trace: selectBuildTrace(report),
        dag: selectBuildDag(report),
      };
    },
  });
}

/**
 * Run read-only inference for the activation-run scaffold and reduce it to the
 * script the build page loads plus its decision trace. Persists nothing.
 */
export function useGenerateActivationScript(reeId?: string) {
  const runtime = useApiRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation<ScriptInferenceOutcome>({
    mutationFn: async () => {
      const report = await runtime.reeApi.generateScriptCandidates(resolvedReeId, [
        { kind: "activation_run" },
      ]);
      const kind: RunTargetKind = "activation_run";
      return {
        generation: selectRunCandidate(report, kind),
        trace: selectRunTrace(report, kind),
        dag: selectRunDag(report, kind),
      };
    },
  });
}

/**
 * Run read-only inference for one experiment's run scaffold. The experiment
 * name selects the target; the returned body becomes a script only when saved.
 */
export function useGenerateExperimentScript(experimentName: string, reeId?: string) {
  const runtime = useApiRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation<ScriptInferenceOutcome>({
    mutationFn: async () => {
      const report = await runtime.reeApi.generateScriptCandidates(resolvedReeId, [
        { kind: "experiment_run", experiment_name: experimentName },
      ]);
      const kind: RunTargetKind = "experiment_run";
      return {
        generation: selectRunCandidate(report, kind, experimentName),
        trace: selectRunTrace(report, kind, experimentName),
        dag: selectRunDag(report, kind, experimentName),
      };
    },
  });
}
