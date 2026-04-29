import type { Dispatch, ReactNode } from "react";
import { createContext, useContext } from "react";
import type { ExplorerRuntimePorts } from "../application/explorer/runtimePorts";
import type { AppAction } from "../context";
import type { IWorkspaceService, WorkspaceServiceLogEntry } from "../services/workspaceService";
import type { FileTreeNode, GenericServiceParams, Ree, ServiceParams } from "../types";

type WorkspaceServiceMode = "remote" | "mock";

interface WorkspaceServiceFactoryArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
  dispatch: Dispatch<AppAction>;
  executeServiceRun: (
    key: string,
    params?: GenericServiceParams,
  ) => Promise<WorkspaceServiceLogEntry>;
}

interface WorkspaceRuntimeValue {
  workspaceId: string;
  workspaceServiceMode: WorkspaceServiceMode;
  ports: ExplorerRuntimePorts;
  createWorkspaceService: (args: WorkspaceServiceFactoryArgs) => IWorkspaceService<FileTreeNode>;
}

const WorkspaceRuntimeContext = createContext<WorkspaceRuntimeValue | null>(null);

interface WorkspaceRuntimeProviderProps {
  children: ReactNode;
  value: WorkspaceRuntimeValue;
}

export function WorkspaceRuntimeProvider({ children, value }: WorkspaceRuntimeProviderProps) {
  return (
    <WorkspaceRuntimeContext.Provider value={value}>{children}</WorkspaceRuntimeContext.Provider>
  );
}

export function useWorkspaceRuntime(): WorkspaceRuntimeValue {
  const value = useContext(WorkspaceRuntimeContext);
  if (!value) {
    throw new Error("useWorkspaceRuntime must be used within WorkspaceRuntimeProvider");
  }
  return value;
}
