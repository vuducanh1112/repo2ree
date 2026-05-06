import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import { appShellPorts } from "../../../shell/app/bootstrap/appShellPorts";
import { useApiRuntime } from "../../../shell/data/apiRuntime";
import { useExecutionRunsClient } from "../../../shell/data/execution-runs/client";
import { useReeClient } from "../../../shell/data/ree/client";
import type { AppShellAction } from "../../../shell/ui/app-shell/state/types";
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
