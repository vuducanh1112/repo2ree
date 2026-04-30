import type { ReactNode } from "react";
import { createContext, useContext } from "react";
import type { WorkspaceBackendGateway } from "../../application/ports/WorkspaceBackendGateway";
import type { WorkspaceEditorRuntimePorts } from "../../application/workspace-editor/WorkspaceEditorPorts";
import type { FileTreeNode } from "../../domain/workspace/FileTree";

export interface WorkspaceRuntimeValue {
  workspaceId: string;
  ports: WorkspaceEditorRuntimePorts;
  workspaceBackend: WorkspaceBackendGateway<FileTreeNode>;
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
