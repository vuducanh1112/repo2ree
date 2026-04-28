import type { ExplorerPage } from "../constants/pages";
import type { Ree } from "./reeModel";
import type {
  WorkflowServiceKey,
  WorkflowServiceParams,
  WorkflowServiceParamsByKey,
  WorkflowServiceRunParams,
  WorkflowServiceRunParamsByKey,
} from "./workflow";

export type {
  ExplorerPage,
  WorkflowServiceKey,
  WorkflowServiceParams,
  WorkflowServiceParamsByKey,
  WorkflowServiceRunParams,
  WorkflowServiceRunParamsByKey,
};

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

export interface ServiceBadge {
  label: string;
  color: string;
  bg: string;
}

export interface ServiceRequire {
  field: keyof Ree;
  label: string;
}

export interface ServiceParam {
  key: string;
  label: string;
  type: "bool" | "select" | "text";
  default: string | boolean;
  hint?: string;
  options?: string[];
}

export type ServiceParamValue = string | boolean;
export type GenericServiceParams = Record<string, ServiceParamValue>;

export interface Service {
  key: string;
  label: string;
  IC: (size?: number) => JSX.Element;
  color: string;
  badge: ServiceBadge;
  desc: string;
  requires: ServiceRequire[];
  params: ServiceParam[];
}

export interface RequirementsBannerProps {
  status: "missing" | "met";
  items?: ServiceRequire[];
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
  idField: keyof Ree;
  idPlaceholder: string;
  params: ServiceParam[];
  requires: ServiceRequire[];
}
