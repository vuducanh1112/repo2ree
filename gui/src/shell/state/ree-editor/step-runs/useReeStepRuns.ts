import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { initialReeStepParams, mergeStepParams } from "@core/ree-steps/stepCatalog";
import { createStepCommandPlanners } from "@core/ree-steps/stepCommands";
import type { ReeStepKey, ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import { activeRunForOperation } from "@core/runs/stepRuns";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeId } from "@shell/data/apiRuntime";
import { useReeRunsClient } from "@shell/data/runs/client";
import { useCancelReeRunMutation, useStartReeRunMutation } from "@shell/data/runs/mutations";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import { setStepParams } from "@shell/state/ree-editor/store/actions";
import type { AppShellAction } from "@shell/state/ree-editor/store/types";
import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { useCallback, useMemo } from "react";
import type { ShowToast } from "../types";
import type { HydratedWorkspaceSnapshot } from "../workspace-sync/hydrateReeWorkspace";
import { createStepRunGateway } from "./stepRunGateway";

interface UseReeStepRunsArgs {
  dispatch: React.Dispatch<AppShellAction>;
  ree: ReeEditorViewModel;
  workspaceFiles: FileTreeNode[];
  persistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  refreshWorkspace: () => Promise<HydratedWorkspaceSnapshot>;
  showToast: ShowToast;
}

export function useReeStepRuns({
  dispatch,
  ree,
  workspaceFiles,
  persistWorkspaceFile,
  refreshWorkspace,
  showToast,
}: UseReeStepRunsArgs) {
  const reeId = useReeId();
  const queryClient = useQueryClient();
  const executionRunsClient = useReeRunsClient();
  const { mutateAsync: startReeRun } = useStartReeRunMutation(reeId);
  const { mutateAsync: cancelReeRun } = useCancelReeRunMutation(reeId);
  const runsQuery = useReeRunsQuery(reeId);
  const runs = runsQuery.data ?? [];
  const getActiveRunId = useCallback(
    (key: string) => activeRunForOperation(runs, key)?.runId,
    [runs],
  );

  const stepCommandPlanners = useMemo(
    () =>
      createStepCommandPlanners({
        ree: ree.spec,
        clock: appShellPorts.clock,
      }),
    [ree],
  );
  const persistGeneratedWorkspaceFile = useCallback(
    (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    [persistWorkspaceFile],
  );
  const persistStepParams = useCallback(
    (key: ReeStepKey, params: GenericReeStepParams) => {
      dispatch(
        setStepParams((prev) =>
          mergeStepParams(
            prev ?? initialReeStepParams(),
            key,
            params as ReeStepRunParams<typeof key>,
          ),
        ),
      );
    },
    [dispatch],
  );
  const startRun = useCallback(
    (scriptKey: string, params?: Record<string, string | boolean | number | null | undefined>) =>
      startReeRun({
        scriptKey,
        params: params as GenericReeStepParams | undefined,
      }),
    [startReeRun],
  );
  const cancelRun = useCallback((runId: string) => cancelReeRun({ runId }), [cancelReeRun]);

  return useMemo(
    () =>
      createStepRunGateway({
        ree,
        workspaceFiles,
        dispatch,
        persistWorkspaceFile: persistGeneratedWorkspaceFile,
        persistStepParams,
        showToast,
        stepCommandPlanners,
        executionRunsClient,
        reeId,
        queryClient,
        startReeRun: startRun,
        cancelReeRun: cancelRun,
        ports: appShellPorts,
        refreshWorkspace,
        getActiveRunId,
      }),
    [
      cancelRun,
      dispatch,
      executionRunsClient,
      getActiveRunId,
      persistGeneratedWorkspaceFile,
      persistStepParams,
      queryClient,
      ree,
      reeId,
      refreshWorkspace,
      showToast,
      startRun,
      stepCommandPlanners,
      workspaceFiles,
    ],
  );
}
