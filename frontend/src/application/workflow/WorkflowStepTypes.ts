import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";

export interface Level {
  n: number;
  label: string;
  color: string;
  bg: string;
  ink: string;
  short: string;
  desc: string;
  problem: string | null;
  fix: string | null;
}

export interface AutomationStepBadge {
  label: string;
  color: string;
  bg: string;
}

export interface AutomationStepRequirement {
  field: keyof ReeDraftViewModel;
  label: string;
}

export interface AutomationStepParam {
  key: string;
  label: string;
  type: "bool" | "select" | "text";
  default: string | boolean;
  hint?: string;
  options?: string[];
}

export type AutomationStepParamValue = string | boolean;
export type GenericAutomationStepParams = Record<string, AutomationStepParamValue>;

export type AutomationStepIconKey = "star" | "cpu" | "chip" | "package" | "shield";

export interface AutomationStepDefinition {
  key: string;
  label: string;
  iconKey: AutomationStepIconKey;
  color: string;
  badge: AutomationStepBadge;
  desc: string;
  params: AutomationStepParam[];
}

export interface RequirementsBannerProps {
  status: "missing" | "met";
  items?: AutomationStepRequirement[];
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
  idField: keyof ReeDraftViewModel;
  idPlaceholder: string;
  params: AutomationStepParam[];
  requires: AutomationStepRequirement[];
}

export type WorkflowBadge = AutomationStepBadge;
export type WorkflowRequirement = AutomationStepRequirement;
export type WorkflowParam = AutomationStepParam;
export type WorkflowParamValue = AutomationStepParamValue;
export type GenericWorkflowParams = GenericAutomationStepParams;
