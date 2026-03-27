import type React from "react";
import type {
  ActionStates,
  Badges,
  FileTreeNode,
  Ree,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
} from "../../../../types";

export type ShowToast = (msg: string, type?: ToastState["type"]) => void;

export interface WorkflowSetters {
  setRee: React.Dispatch<React.SetStateAction<Ree>>;
  setLocked: React.Dispatch<React.SetStateAction<boolean>>;
  setActionStates: React.Dispatch<React.SetStateAction<ActionStates>>;
  setBadges: React.Dispatch<React.SetStateAction<Badges>>;
  setTimestamps: React.Dispatch<React.SetStateAction<Timestamps>>;
  setServiceLogs: React.Dispatch<React.SetStateAction<ServiceLogs>>;
  setServiceParams: React.Dispatch<React.SetStateAction<ServiceParams>>;
  setToast: React.Dispatch<React.SetStateAction<ToastState | null>>;
  setVirtualFiles: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  setImmutableSourceSnapshotFiles: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  setImmutableSourceSnapshotArchiveName: React.Dispatch<React.SetStateAction<string>>;
}
