import { useCallback, useMemo } from "react";
import type { WorkflowParamValue } from "../../../application/workflow/WorkflowStepTypes";
import type { AutomationStepRunParams } from "../../../application/workflow/WorkflowTypes";
import {
  AUTOMATION_STEPS,
  defaultParamsForAutomationStep,
} from "../../../application/workflow/workflowCatalog";
import { missingWorkflowRequirements } from "../../../application/workflow/workflowPolicies";
import { workspaceShellPageForField } from "../../../application/workspace-shell/WorkspaceShellNavigation";
import type { useWorkspaceShell } from "./useWorkspaceShell";

type WorkspaceShellController = ReturnType<typeof useWorkspaceShell>;

interface UseWorkflowStepPageControllerArgs {
  state: WorkspaceShellController["state"];
  commands: WorkspaceShellController["commands"];
}

export function useWorkflowStepPageController({
  state,
  commands,
}: UseWorkflowStepPageControllerArgs) {
  const { page, ree, badges, workflowLogs, workflowParams, actionStates, timestamps } = state;

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
        ? workspaceShellPageForField(String(firstMissingField))
        : workspaceShellPageForField("name"),
    );
  }, [commands, missing]);

  if (!workflowStep || !params) {
    return null;
  }

  return {
    workflowStep,
    log: workflowLogs[workflowStep.key],
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
