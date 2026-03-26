import type { LogEntry } from "./ree";

export interface FileTreeNode {
  id: string;
  name: string;
  type: "file" | "folder";
  content?: string;
  tag?: string;
  children?: FileTreeNode[];
}

export interface IWorkspaceService {
  getWorkspace(): Promise<FileTreeNode[]>;
  updateFile(path: string, content: string): Promise<void>;
  runScript(path: string): Promise<WorkspaceServiceLogEntry[]>;
  resetWorkspace(mode: "download" | "upload" | "clear"): Promise<void>;
}

export interface WorkspaceServiceLogEntry extends LogEntry {
  // Extends LogEntry from ree.ts
}
