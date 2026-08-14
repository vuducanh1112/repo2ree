import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { initialReeStepParams, mergeStepParams } from "@core/ree-steps/stepCatalog";
import { createStepCommandPlanners } from "@core/ree-steps/stepCommands";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeId } from "@shell/data/apiRuntime";
import { useReeRunsClient } from "@shell/data/runs/client";
import { useCancelReeRunMutation, useStartReeRunMutation } from "@shell/data/runs/mutations";
import { setStepParams } from "@shell/ui/app-shell/state/actions";
import type { AppShellAction } from "@shell/ui/app-shell/state/types";
import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
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
  getActiveRunId: (key: string) => string | undefined;
}

export function useReeStepRuns({
  dispatch,
  ree,
  workspaceFiles,
  persistWorkspaceFile,
  refreshWorkspace,
  showToast,
  getActiveRunId,
}: UseReeStepRunsArgs) {
  const reeId = useReeId();
  const queryClient = useQueryClient();
  const executionRunsClient = useReeRunsClient();
  const startReeRunMutation = useStartReeRunMutation(reeId);
  const cancelReeRunMutation = useCancelReeRunMutation(reeId);

  const stepCommandPlanners = createStepCommandPlanners({
    ree,
    clock: appShellPorts.clock,
  });

  return createStepRunGateway({
    ree,
    workspaceFiles,
    dispatch,
    persistWorkspaceFile: (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    persistStepParams: (key, params) => {
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
    showToast,
    stepCommandPlanners,
    executionRunsClient,
    reeId,
    queryClient,
    startReeRun: (scriptKey, params) =>
      startReeRunMutation.mutateAsync({
        scriptKey,
        params: params as GenericReeStepParams | undefined,
      }),
    cancelReeRun: (runId) => cancelReeRunMutation.mutateAsync({ runId }),
    ports: appShellPorts,
    refreshWorkspace,
    getActiveRunId,
  });
}
