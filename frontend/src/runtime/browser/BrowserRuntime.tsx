import type { Dispatch, ReactNode } from "react";
import { createContext, useContext } from "react";
import type {
  WorkflowRunLogEntry,
  WorkspaceGateway,
} from "../../application/ports/WorkspaceGateway";
import type { GenericServiceParams } from "../../application/workflow/WorkflowStepTypes";
import type { WorkspaceEditorAction } from "../../application/workspace-editor";
import type { WorkspaceEditorRuntimePorts } from "../../application/workspace-editor/WorkspaceEditorPorts";
import type { Ree } from "../../domain/ree/ReeSpec";
import type { ServiceParams } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";

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
