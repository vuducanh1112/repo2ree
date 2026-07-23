import type { DecisionDag, DecisionTrace } from "@shell/infra/api/apiTypes";
import { useMutation } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { type ScriptTargetKind, selectCandidate, selectDag, selectTrace } from "./candidate";
import type { ScriptGeneration } from "./generation";

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
  return useGenerateScriptForTarget("build", undefined, reeId);
}

/**
 * Run read-only inference for the activation-run scaffold and reduce it to the
 * script the build page loads plus its decision trace. Persists nothing.
 */
export function useGenerateActivationScript(reeId?: string) {
  return useGenerateScriptForTarget("activation_run", undefined, reeId);
}

/**
 * Run read-only inference for one experiment's run scaffold. The experiment
 * name selects the target; the returned body becomes a script only when saved.
 */
export function useGenerateExperimentScript(experimentName: string, reeId?: string) {
  return useGenerateScriptForTarget("experiment_run", experimentName, reeId);
}

// The one generate mutation. Every target requests its own inference report and
// reduces it identically, so the per-page hooks above only name their target.
function useGenerateScriptForTarget(
  kind: ScriptTargetKind,
  experimentName: string | undefined,
  reeId: string | undefined,
) {
  const runtime = useApiRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation<ScriptInferenceOutcome>({
    mutationFn: async () => {
      const report = await runtime.reeApi.generateScriptCandidates(resolvedReeId, [
        experimentName ? { kind, experiment_name: experimentName } : { kind },
      ]);
      return {
        generation: selectCandidate(report, kind, experimentName),
        trace: selectTrace(report, kind, experimentName),
        dag: selectDag(report, kind, experimentName),
      };
    },
  });
}
