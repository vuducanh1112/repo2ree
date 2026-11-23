import type { DecisionDag, DecisionTrace } from "@shell/infra/api/apiTypes";
import { useMutation } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { type ScriptTargetKind, selectCandidate, selectDag, selectTrace } from "./candidate";
import type { ScriptGeneration } from "./generation";

export interface ScriptInferenceOutcome {
  generation: ScriptGeneration;
  trace: DecisionTrace | null;
  dag: DecisionDag | null;
}

export function useGenerateBuildExperimentEnvironmentScript(reeId?: string) {
  return useGenerateScriptForTarget("build_experiment_environment", undefined, reeId);
}

export function useGenerateActivateExperimentEnvironmentScript(reeId?: string) {
  return useGenerateScriptForTarget("activate_experiment_environment", undefined, reeId);
}

export function useGenerateExperimentScript(experimentName: string, reeId?: string) {
  return useGenerateScriptForTarget("experiment_run", experimentName, reeId);
}

function useGenerateScriptForTarget(
  kind: ScriptTargetKind,
  experimentName: string | undefined,
  reeId: string | undefined,
) {
  const runtime = useReeRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation<ScriptInferenceOutcome>({
    mutationFn: async () => {
      const report = await runtime.reeApi.suggestScripts(resolvedReeId, [
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
