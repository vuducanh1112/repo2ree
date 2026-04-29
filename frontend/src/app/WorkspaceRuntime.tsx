import type { Dispatch, ReactNode } from "react";
import { createContext, useContext } from "react";
import type { WorkspaceEditorRuntimePorts } from "../application/workspace/workspaceEditorPorts";
import type { WorkspaceEditorAction } from "../context";
import type { FileTreeNode, GenericServiceParams, Ree, ServiceParams } from "../types";
import type { WorkflowRunLogEntry, WorkspaceGateway } from "../workspace/WorkspaceGateway";

type WorkspaceServiceMode = "remote" | "mock";

export interface WorkspaceServiceFactoryArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
  dispatch: Dispatch<WorkspaceEditorAction>;
  executeServiceRun: (key: string, params?: GenericServiceParams) => Promise<WorkflowRunLogEntry>;
}

export interface WorkspaceRuntimeValue {
  workspaceId: string;
  workspaceServiceMode: WorkspaceServiceMode;
  ports: WorkspaceEditorRuntimePorts;
  createWorkspaceService: (args: WorkspaceServiceFactoryArgs) => WorkspaceGateway<FileTreeNode>;
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
