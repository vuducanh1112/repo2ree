import type { DecisionDag, DecisionTrace } from "@shell/infra/api/apiTypes";
import { useMutation } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import {
  type BuildScriptGeneration,
  selectBuildCandidate,
  selectBuildDag,
  selectBuildTrace,
} from "./buildCandidate";

interface BuildInferenceOutcome {
  generation: BuildScriptGeneration;
  // The executed decision-DAG walk for the build target — the explanation of
  // what inference did. Null only if the report has no build target.
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

  return useMutation<BuildInferenceOutcome>({
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
