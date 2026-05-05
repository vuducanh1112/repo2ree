import { useCallback, useMemo } from "react";
import { appShellPageForField } from "../../../application/state/pages";
import type { WorkflowParamValue } from "../../../application/workflow/WorkflowStepTypes";
import type { AutomationStepRunParams } from "../../../application/workflow/WorkflowTypes";
import {
  AUTOMATION_STEPS,
  defaultParamsForAutomationStep,
} from "../../../application/workflow/workflowCatalog";
import { missingWorkflowRequirements } from "../../../application/workflow/workflowPolicies";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useWorkflowRunLogsQuery, useWorkflowRunQuery } from "../../../data/workflow-runs/queries";
import type { WorkflowRunRecord } from "../../../domain/workflow/WorkflowRun";
import type { useAppShell } from "./useAppShell";

type AppShellController = ReturnType<typeof useAppShell>;

interface UseWorkflowStepPageControllerArgs {
  ree: AppShellController["ree"];
  workflowRun: AppShellController["workflowRun"];
  uiChrome: AppShellController["uiChrome"];
  commands: AppShellController["commands"];
}

export function useWorkflowStepPageController({
  ree,
  workflowRun,
  uiChrome,
  commands,
}: UseWorkflowStepPageControllerArgs) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, workflowParams, actionStates, timestamps, activeRunIds } = workflowRun;

  const workflowStep = useMemo(() => AUTOMATION_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!workflowStep) {
      return [];
    }
    return missingWorkflowRequirements(workflowStep.key, ree);
  }, [workflowStep, ree]);

  const params = useMemo(() => {
    if (!workflowStep) {
      return null;
    }
    return (
      (workflowParams[workflowStep.key] as AutomationStepRunParams | undefined) ??
      defaultParamsForAutomationStep(workflowStep.key)
    );
  }, [workflowStep, workflowParams]);

  const setParam = useCallback(
    (paramKey: string, value: WorkflowParamValue) => {
      if (!workflowStep) {
        return;
      }

      commands.setWorkflowParams((previous) => ({
        ...previous,
        [workflowStep.key]: {
          ...(previous[workflowStep.key] ?? defaultParamsForAutomationStep(workflowStep.key)),
          [paramKey]: value,
        },
      }));
    },
    [workflowStep, commands],
  );

  const goToRequirements = useCallback(() => {
    const firstMissingField = missing[0]?.field;
    commands.setPage(
      firstMissingField
        ? appShellPageForField(String(firstMissingField))
        : appShellPageForField("name"),
    );
  }, [commands, missing]);

  const runId = workflowStep ? activeRunIds[workflowStep.key] : undefined;
  const runQuery = useWorkflowRunQuery(reeId, runId);
  const logsQuery = useWorkflowRunLogsQuery(reeId, runId);
  const log = useMemo(() => {
    if (!workflowStep || !runId) {
      return null;
    }
    const runTimestamp = resolveWorkflowRunTimestamp(runQuery.data, timestamps[workflowStep.key]);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [logsQuery.data?.lines, runId, runQuery.data, timestamps, workflowStep]);

  if (!workflowStep || !params) {
    return null;
  }

  return {
    workflowStep,
    log,
    running: actionStates[workflowStep.key] === "loading",
    runDone: !!badges[workflowStep.key],
    badge: badges[workflowStep.key] ? workflowStep.badge : null,
    ts: timestamps[workflowStep.key],
    missing,
    params,
    setParam,
    goToRequirements,
  };
}

function resolveWorkflowRunTimestamp(
  run: WorkflowRunRecord | undefined,
  fallback?: string,
): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}
