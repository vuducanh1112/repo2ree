import type { ReeSpec } from "../ree/ReeSpec";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";

export interface ReeStepBadge {
  label: string;
  color: string;
  bg: string;
}

export interface ReeStepRequirement {
  field: keyof ReeSpec | keyof WorkspaceSourceState;
  label: string;
}

export interface ReeStepParam {
  key: string;
  label: string;
  type: "bool" | "select" | "text";
  default: string | boolean;
  hint?: string;
  options?: string[];
}

export type ReeStepParamValue = string | boolean;
export type GenericReeStepParams = Record<string, ReeStepParamValue>;

export type ReeStepIconKey = "star" | "cpu" | "chip" | "package" | "shield";

export interface ReeStepDefinition {
  key: string;
  label: string;
  iconKey: ReeStepIconKey;
  color: string;
  badge: ReeStepBadge;
  desc: string;
  params: ReeStepParam[];
}

export interface ToastState {
  message: string;
  type: "info" | "success" | "error";
}

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
  params: ReeStepParam[];
  requires: ReeStepRequirement[];
}
