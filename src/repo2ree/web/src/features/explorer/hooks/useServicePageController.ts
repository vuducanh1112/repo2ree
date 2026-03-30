import { useCallback, useMemo } from "react";
import { PAGE } from "../../../constants/pages";
import { defaultParamsForService, SERVICES } from "../../../constants/services";
import type { Ree, ServiceParamValue, WorkflowServiceRunParams } from "../../../types";
import { missingRequirements } from "../utils/requirements";
import type { useExplorerController } from "./useExplorerController";

type ExplorerController = ReturnType<typeof useExplorerController>;

interface UseServicePageControllerArgs {
  state: ExplorerController["state"];
  commands: ExplorerController["commands"];
}

export function useServicePageController({ state, commands }: UseServicePageControllerArgs) {
  const { page, ree, badges, serviceLogs, serviceParams, actionStates, timestamps } = state;

  const service = useMemo(() => SERVICES.find((svc) => svc.key === page), [page]);

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
      (serviceParams[service.key] as WorkflowServiceRunParams | undefined) ??
      defaultParamsForService(service)
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
          ...(previous[service.key] ?? defaultParamsForService(service)),
          [paramKey]: value,
        },
      }));
    },
    [service, commands],
  );

  const goToRequirements = useCallback(() => {
    const sourceFieldKeys: (keyof Ree)[] = ["origin_url", "source_type", "_sourceAvailable"];
    const hasSourceGap = missing.some((requirement) => sourceFieldKeys.includes(requirement.field));
    commands.setPage(hasSourceGap ? PAGE.SOURCE : PAGE.METADATA);
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
