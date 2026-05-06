import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
import type { ReeEditorViewModel } from "../../../application/ree-editor/reeEditorViewModel";
import type { AppShellAction } from "../../../application/state/types";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useExecutionRunsClient } from "../../../data/execution-runs/client";
import { useReeClient } from "../../../data/ree/client";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "../types";
import { createSourceActions } from "./sourceActions";

interface UseSourceAcquisitionArgs {
  dispatch: React.Dispatch<AppShellAction>;
  ree: ReeEditorViewModel;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function useSourceAcquisition({
  dispatch,
  ree,
  refreshWorkspaceFiles,
  showToast,
  onRunStarted,
  onRunFinished,
}: UseSourceAcquisitionArgs) {
  const { reeId } = useApiRuntime();
  const queryClient = useQueryClient();
  const reeClient = useReeClient();
  const executionRunsClient = useExecutionRunsClient();

  return createSourceActions({
    ree,
    reeClient,
    executionRunsClient,
    reeId,
    queryClient,
    dispatch,
    refreshWorkspaceFiles,
    showToast,
    clock: appShellPorts.clock,
    sleep: appShellPorts.sleep,
    onRunStarted,
    onRunFinished,
  });
}
