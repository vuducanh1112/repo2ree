import { useCallback, useMemo } from "react";
import {
  defaultParamsForReeAssemblyOperation,
  REE_ASSEMBLY_STEPS,
} from "../../../application/ree-assembly/assemblyCatalog";
import { missingReeAssemblyRequirements } from "../../../application/ree-assembly/assemblyPolicies";
import type { ReeAssemblyParamValue } from "../../../application/ree-assembly/assemblyStepTypes";
import type { ReeAssemblyRunParams } from "../../../application/ree-assembly/assemblyTypes";
import { appShellPageForField } from "../../../application/state/pages";
import { useApiRuntime } from "../../../data/apiRuntime";
import {
  useExecutionRunLogsQuery,
  useExecutionRunQuery,
} from "../../../data/execution-runs/queries";
import type { ExecutionRun } from "../../../domain/execution/ExecutionRun";
import type { useAppShell } from "./useAppShell";

type AppShellController = ReturnType<typeof useAppShell>;

interface UseAssemblyStepPageControllerArgs {
  ree: AppShellController["ree"];
  assemblyRun: AppShellController["assemblyRun"];
  uiChrome: AppShellController["uiChrome"];
  commands: AppShellController["commands"];
}

export function useAssemblyStepPageController({
  ree,
  assemblyRun,
  uiChrome,
  commands,
}: UseAssemblyStepPageControllerArgs) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { badges, assemblyOperationParams, actionStates, timestamps, activeRunIds } = assemblyRun;

  const assemblyStep = useMemo(() => REE_ASSEMBLY_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!assemblyStep) {
      return [];
    }
    return missingReeAssemblyRequirements(assemblyStep.key, ree);
  }, [assemblyStep, ree]);

  const params = useMemo(() => {
    if (!assemblyStep) {
      return null;
    }
    return (
      (assemblyOperationParams[assemblyStep.key] as ReeAssemblyRunParams | undefined) ??
      defaultParamsForReeAssemblyOperation(assemblyStep.key)
    );
  }, [assemblyStep, assemblyOperationParams]);

  const setParam = useCallback(
    (paramKey: string, value: ReeAssemblyParamValue) => {
      if (!assemblyStep) {
        return;
      }

      commands.setAssemblyOperationParams((previous) => ({
        ...previous,
        [assemblyStep.key]: {
          ...(previous[assemblyStep.key] ?? defaultParamsForReeAssemblyOperation(assemblyStep.key)),
          [paramKey]: value,
        },
      }));
    },
    [assemblyStep, commands],
  );

  const goToRequirements = useCallback(() => {
    const firstMissingField = missing[0]?.field;
    commands.setPage(
      firstMissingField
        ? appShellPageForField(String(firstMissingField))
        : appShellPageForField("name"),
    );
  }, [commands, missing]);

  const runId = assemblyStep ? activeRunIds[assemblyStep.key] : undefined;
  const runQuery = useExecutionRunQuery(reeId, runId);
  const logsQuery = useExecutionRunLogsQuery(reeId, runId);
  const log = useMemo(() => {
    if (!assemblyStep || !runId) {
      return null;
    }
    const runTimestamp = resolveAssemblyRunTimestamp(runQuery.data, timestamps[assemblyStep.key]);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [logsQuery.data?.lines, runId, runQuery.data, timestamps, assemblyStep]);

  if (!assemblyStep || !params) {
    return null;
  }

  return {
    assemblyStep,
    log,
    running: actionStates[assemblyStep.key] === "loading",
    runDone: !!badges[assemblyStep.key],
    badge: badges[assemblyStep.key] ? assemblyStep.badge : null,
    ts: timestamps[assemblyStep.key],
    missing,
    params,
    setParam,
    goToRequirements,
  };
}

function resolveAssemblyRunTimestamp(run: ExecutionRun | undefined, fallback?: string): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}
