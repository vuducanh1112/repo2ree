import type { ReeSpec } from "../ree/ReeSpec";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";

export type { Level } from "../review/Level";

export interface ReeAssemblyBadge {
  label: string;
  color: string;
  bg: string;
}

export interface ReeAssemblyRequirement {
  field: keyof ReeSpec | keyof WorkspaceSourceState;
  label: string;
}

export interface ReeAssemblyParam {
  key: string;
  label: string;
  type: "bool" | "select" | "text";
  default: string | boolean;
  hint?: string;
  options?: string[];
}

export type ReeAssemblyParamValue = string | boolean;
export type GenericReeAssemblyParams = Record<string, ReeAssemblyParamValue>;

export type ReeAssemblyIconKey = "star" | "cpu" | "chip" | "package" | "shield";

export interface ReeAssemblyDefinition {
  key: string;
  label: string;
  iconKey: ReeAssemblyIconKey;
  color: string;
  badge: ReeAssemblyBadge;
  desc: string;
  params: ReeAssemblyParam[];
}

export interface RequirementsBannerProps {
  status: "missing" | "met";
  items?: ReeAssemblyRequirement[];
  onAction?: () => void;
  actionLabel?: string;
}

export interface ToastState {
  message: string;
  type: "info" | "success" | "error";
}

export type StepState = "idle" | "loading" | "done";

export interface ArchiveRepo {
  key: string;
  label: string;
  shortLabel: string;
  color: string;
  bg: string;
  border: string;
  url: string;
  desc: string;
  idLabel: string;
  idField: keyof ReeSpec;
  idPlaceholder: string;
  params: ReeAssemblyParam[];
  requires: ReeAssemblyRequirement[];
}
