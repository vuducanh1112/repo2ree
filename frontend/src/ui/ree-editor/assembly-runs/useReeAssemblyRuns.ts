import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { initialReeAssemblyOperationParams } from "../../../core/ree-assembly/assemblyCatalog";
import { createAssemblyCommandPlanners } from "../../../core/ree-assembly/assemblyCommands";
import type { createAssemblyRunSession } from "../../../core/ree-assembly/assemblyRunSession";
import type { GenericReeAssemblyParams } from "../../../core/ree-assembly/assemblyStepTypes";
import type { ReeAssemblyRunParams } from "../../../core/ree-assembly/assemblyTypes";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import { appShellPorts } from "../../../shell/app/bootstrap/appShellPorts";
import { useApiRuntime } from "../../../shell/data/apiRuntime";
import { useExecutionRunsClient } from "../../../shell/data/execution-runs/client";
import {
  useCancelExecutionRunMutation,
  useStartExecutionRunMutation,
} from "../../../shell/data/execution-runs/mutations";
import { setAssemblyOperationParams } from "../../../shell/ui/app-shell/state/actions";
import type { AppShellAction } from "../../../shell/ui/app-shell/state/types";
import type { ShowToast } from "../types";
import type { HydratedWorkspaceSnapshot } from "../workspace-sync/hydrateReeWorkspace";
import { createAssemblyRunGateway } from "./assemblyRunGateway";

interface UseReeAssemblyRunsArgs {
  dispatch: React.Dispatch<AppShellAction>;
  ree: ReeEditorViewModel;
  level: number;
  workspaceFiles: FileTreeNode[];
  persistWorkspaceFile: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  refreshWorkspace: () => Promise<HydratedWorkspaceSnapshot>;
  showToast: ShowToast;
  runSession: ReturnType<typeof createAssemblyRunSession>;
}

export function useReeAssemblyRuns({
  dispatch,
  ree,
  level,
  workspaceFiles,
  persistWorkspaceFile,
  refreshWorkspace,
  showToast,
  runSession,
}: UseReeAssemblyRunsArgs) {
  const { reeId } = useApiRuntime();
  const queryClient = useQueryClient();
  const executionRunsClient = useExecutionRunsClient();
  const startExecutionRunMutation = useStartExecutionRunMutation(reeId);
  const cancelExecutionRunMutation = useCancelExecutionRunMutation(reeId);

  const assemblyCommandPlanners = createAssemblyCommandPlanners({
    ree,
    workspaceFiles,
    clock: appShellPorts.clock,
  });

  return createAssemblyRunGateway({
    ree,
    level,
    workspaceFiles,
    dispatch,
    persistWorkspaceFile: (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    persistAssemblyParams: (key, params) => {
      dispatch(
        setAssemblyOperationParams((prev) =>
          runSession.mergeAssemblyOperationParams(
            prev ?? initialReeAssemblyOperationParams(),
            key,
            params as ReeAssemblyRunParams<typeof key>,
          ),
        ),
      );
    },
    showToast,
    assemblyCommandPlanners,
    executionRunsClient,
    reeId,
    queryClient,
    startExecutionRun: (scriptKey, params) =>
      startExecutionRunMutation.mutateAsync({
        scriptKey,
        params: params as GenericReeAssemblyParams | undefined,
      }),
    cancelExecutionRun: (runId) => cancelExecutionRunMutation.mutateAsync({ runId }),
    ports: appShellPorts,
    refreshWorkspace,
    runSession,
  });
}
