import type { ReactNode } from "react";
import { createContext, useContext } from "react";
import type { AppShellRuntimePorts } from "../../application/app-shell/AppShellPorts";
import type { ArtifactRepository } from "../../application/ports/ArtifactRepository";
import type { ReviewRepository } from "../../application/ports/ReviewRepository";
import type { WorkflowRunRepository } from "../../application/ports/WorkflowRunRepository";
import type { WorkspaceRepository } from "../../application/ports/WorkspaceRepository";
import type { FileTreeNode } from "../../domain/workspace/FileTree";

export interface WorkspaceRuntimeValue {
  workspaceId: string;
  ports: AppShellRuntimePorts;
  workspaceRepository: WorkspaceRepository<FileTreeNode>;
  workflowRunRepository: WorkflowRunRepository;
  artifactRepository: ArtifactRepository;
  reviewRepository: ReviewRepository;
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
