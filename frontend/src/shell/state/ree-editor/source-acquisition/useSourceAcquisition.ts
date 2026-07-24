import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useReeClient } from "@shell/data/ree/client";
import { useReeRunsClient } from "@shell/data/runs/client";
import type { AppShellAction } from "@shell/ui/app-shell/state/types";
import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import type { ShowToast } from "../types";
import { createSourceActions } from "./sourceActions";

interface UseSourceAcquisitionArgs {
  dispatch: React.Dispatch<AppShellAction>;
  ree: ReeEditorViewModel;
  refreshWorkspaceFiles: (options?: { forceReeHydration?: boolean }) => Promise<FileTreeNode[]>;
  showToast: ShowToast;
}

export function useSourceAcquisition({
  dispatch,
  ree,
  refreshWorkspaceFiles,
  showToast,
}: UseSourceAcquisitionArgs) {
  const { reeId } = useApiRuntime();
  const queryClient = useQueryClient();
  const reeClient = useReeClient();
  const executionRunsClient = useReeRunsClient();

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
  });
}
