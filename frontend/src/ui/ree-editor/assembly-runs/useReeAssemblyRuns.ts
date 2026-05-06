import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
import { initialReeAssemblyOperationParams } from "../../../application/ree-assembly/assemblyCatalog";
import { createAssemblyCommandPlanners } from "../../../application/ree-assembly/assemblyCommands";
import type { createAssemblyRunSession } from "../../../application/ree-assembly/assemblyRunSession";
import type { GenericReeAssemblyParams } from "../../../application/ree-assembly/assemblyStepTypes";
import type { ReeAssemblyRunParams } from "../../../application/ree-assembly/assemblyTypes";
import type { ReeEditorViewModel } from "../../../application/ree-editor/reeEditorViewModel";
import { patch } from "../../../application/state/actions";
import type { AppShellAction } from "../../../application/state/types";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useExecutionRunsClient } from "../../../data/execution-runs/client";
import {
  useCancelExecutionRunMutation,
  useStartExecutionRunMutation,
} from "../../../data/execution-runs/mutations";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
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
        patch("workflowRun", (prev) => ({
          workflowParams: runSession.mergeAssemblyOperationParams(
            prev.workflowParams ?? initialReeAssemblyOperationParams(),
            key,
            params as ReeAssemblyRunParams<typeof key>,
          ),
        })),
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
