import { useCallback, useMemo } from "react";
import { AUTOMATION_STEPS, defaultParamsForAutomationStep } from "../../../constants/services";
import type { AutomationStepRunParams, ServiceParamValue } from "../../../types";
import { explorerPageForField } from "../utils/navigation";
import { missingRequirements } from "../utils/requirements";
import type { useExplorerController } from "./useExplorerController";

type ExplorerController = ReturnType<typeof useExplorerController>;

interface UseServicePageControllerArgs {
  state: ExplorerController["state"];
  commands: ExplorerController["commands"];
}

export function useServicePageController({ state, commands }: UseServicePageControllerArgs) {
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
        ? explorerPageForField(String(firstMissingField))
        : explorerPageForField("name"),
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
