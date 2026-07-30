import { isFailedStepOutcome } from "@core/ree/ReeTypes";
import { defaultParamsForReeStep, REE_STEPS } from "@core/ree-steps/stepCatalog";
import { missingReeStepRequirements } from "@core/ree-steps/stepPolicies";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { ReeStepParamValue } from "@core/ree-steps/stepTypes";
import type { ReeRun } from "@core/runs/ReeRun";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useReeRunLogsQuery, useReeRunQuery } from "@shell/data/runs/queries";
import { useCallback, useMemo } from "react";
import { appShellPageForField } from "../state/pages";
import type { useAppShell } from "./useAppShell";

type AppShellController = ReturnType<typeof useAppShell>;

interface UseStepPageControllerArgs {
  ree: AppShellController["ree"];
  stepRuns: AppShellController["stepRuns"];
  uiChrome: AppShellController["uiChrome"];
  commands: AppShellController["commands"];
}

export function useStepPageController({
  ree,
  stepRuns,
  uiChrome,
  commands,
}: UseStepPageControllerArgs) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, stepParams, actionStates, timestamps, activeRunIds } = stepRuns;
  const step = useMemo(() => REE_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!step) {
      return [];
    }
    return missingReeStepRequirements(step.key, ree);
  }, [step, ree]);

  const params = useMemo(() => {
    if (!step) {
      return null;
    }
    return (
      (stepParams[step.key] as ReeStepRunParams | undefined) ?? defaultParamsForReeStep(step.key)
    );
  }, [step, stepParams]);

  const setParam = useCallback(
    (paramKey: string, value: ReeStepParamValue) => {
      if (!step) {
        return;
      }

      commands.setStepParams((previous) => ({
        ...previous,
        [step.key]: {
          ...(previous[step.key] ?? defaultParamsForReeStep(step.key)),
          [paramKey]: value,
        },
      }));
    },
    [step, commands],
  );

  const goToRequirements = useCallback(() => {
    const firstMissingField = missing[0]?.field;
    commands.setPage(
      firstMissingField
        ? appShellPageForField(String(firstMissingField))
        : appShellPageForField("name"),
    );
  }, [commands, missing]);

  const runId = step ? activeRunIds[step.key] : undefined;
  const runQuery = useReeRunQuery(reeId, runId);
  const logsQuery = useReeRunLogsQuery(reeId, runId);
  const log = useMemo(() => {
    if (!step || !runId) {
      return null;
    }
    const runTimestamp = resolveStepRunTimestamp(runQuery.data, timestamps[step.key]);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [logsQuery.data?.lines, runId, runQuery.data, timestamps, step]);

  if (!step || !params) {
    return null;
  }

  const badgeEntry = badges[step.key];
  const runFailed = isFailedStepOutcome(badgeEntry);
  return {
    step,
    log,
    running: actionStates[step.key] === "loading",
    runDone: !!badgeEntry,
    runFailed,
    // The catalog badge is an earned marker — a failed run completes the step
    // (Re-run appears) but earns nothing.
    badge: badgeEntry && !runFailed ? step.badge : null,
    ts: timestamps[step.key],
    missing,
    params,
    setParam,
    goToRequirements,
  };
}

function resolveStepRunTimestamp(run: ReeRun | undefined, fallback?: string): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}
