import { useApiServices, useReeRuntime } from "@shell/data/apiRuntime";
import { resolveReeId } from "@shell/data/client";
import { queryKeys } from "@shell/data/queryKeys";
import type {
  LintReport,
  LintScriptsResponse,
  ScriptTargetSelector,
} from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import type { LintTarget } from "./findings";

function selector(target: LintTarget): ScriptTargetSelector {
  return target.experimentName
    ? { kind: target.kind, experiment_name: target.experimentName }
    : { kind: target.kind };
}

/** The report for one target, or undefined when that script is not written yet. */
export function selectReport(
  response: LintScriptsResponse | undefined,
  target: LintTarget,
): LintReport | undefined {
  return response?.reports?.find(
    (report) =>
      report.target.kind === target.kind &&
      (report.target.experiment_name ?? null) === (target.experimentName ?? null),
  );
}

/** Contract-tier checks over unsaved source. */
export function useScriptDraftLint(
  target: LintTarget,
  source: string,
  runtimePath: string | null,
  options: { enabled: boolean },
) {
  const { reeApi } = useApiServices();
  return useQuery<LintReport>({
    queryKey: queryKeys.scriptLintDraft(target.kind, target.experimentName ?? "", source),
    queryFn: async () =>
      reeApi.checkScriptDraft(selector(target), source, { runtime_path: runtimePath }),
    enabled: options.enabled && source.trim() !== "",
    staleTime: Number.POSITIVE_INFINITY,
    // Avoid flicker while a newer draft is checked.
    placeholderData: (previous) => previous,
    retry: false,
  });
}

/** Every available tier over one saved script. */
export function useSavedScriptLint(
  target: LintTarget,
  savedSource: string,
  options: { enabled: boolean },
  reeId?: string,
) {
  const runtime = useReeRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);
  return useQuery<LintReport | undefined>({
    queryKey: queryKeys.scriptLintSaved(
      resolvedReeId,
      target.kind,
      target.experimentName ?? "",
      savedSource,
    ),
    queryFn: async () =>
      selectReport(await runtime.reeApi.lintReeScripts(resolvedReeId, [selector(target)]), target),
    enabled: options.enabled && savedSource.trim() !== "",
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}
