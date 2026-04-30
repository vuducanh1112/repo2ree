import { useCallback, useMemo } from "react";
import {
  AUTOMATION_STEPS,
  defaultParamsForAutomationStep,
} from "../../../application/workflow/WorkflowStepDefinitions";
import type { ServiceParamValue } from "../../../application/workflow/WorkflowStepTypes";
import type { AutomationStepRunParams } from "../../../application/workflow/WorkflowTypes";
import { workspaceEditorPageForField } from "../../../application/workspace-editor/WorkspaceEditorNavigation";
import { missingRequirements } from "../orchestration/requirements";
import type { useWorkspaceEditor } from "./useWorkspaceEditor";

type WorkspaceEditorController = ReturnType<typeof useWorkspaceEditor>;

interface UseWorkflowStepPageControllerArgs {
  state: WorkspaceEditorController["state"];
  commands: WorkspaceEditorController["commands"];
}

export function useWorkflowStepPageController({
  state,
  commands,
}: UseWorkflowStepPageControllerArgs) {
  const { page, ree, badges, serviceLogs, serviceParams, actionStates, timestamps } = state;

  const service = useMemo(() => AUTOMATION_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!service) {
      return [];
    }
    return missingRequirements(service, ree);
  }, [service, ree]);

  const params = useMemo(() => {
    if (!service) {
      return null;
    }
    return (
      (serviceParams[service.key] as AutomationStepRunParams | undefined) ??
      defaultParamsForAutomationStep(service)
    );
  }, [service, serviceParams]);

  const setParam = useCallback(
    (paramKey: string, value: ServiceParamValue) => {
      if (!service) {
        return;
      }

      commands.setServiceParams((previous) => ({
        ...previous,
        [service.key]: {
          ...(previous[service.key] ?? defaultParamsForAutomationStep(service)),
          [paramKey]: value,
        },
      }));
    },
    [service, commands],
  );

  const goToRequirements = useCallback(() => {
    const firstMissingField = missing[0]?.field;
    commands.setPage(
      firstMissingField
        ? workspaceEditorPageForField(String(firstMissingField))
        : workspaceEditorPageForField("name"),
    );
  }, [commands, missing]);

  if (!service || !params) {
    return null;
  }

  return {
    service,
    log: serviceLogs[service.key],
    running: actionStates[service.key] === "loading",
    runDone: !!badges[service.key],
    badge: badges[service.key] ? service.badge : null,
    ts: timestamps[service.key],
    missing,
    params,
    setParam,
    goToRequirements,
  };
}
