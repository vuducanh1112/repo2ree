import type { ExplorerPage } from "../constants/pages";
import type { Ree } from "./ree";

export type { ExplorerPage };

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

export type WorkflowServiceKey = "evaluate" | "build" | "sbom" | "activation";

export interface WorkflowServiceParamsByKey {
  evaluate: {
    strict: boolean;
    swhid_check: boolean;
  };
  build: {
    no_cache: boolean;
    platform: string;
  };
  sbom: {
    format: string;
  };
  activation: {
    timeout: string;
    verbose: boolean;
  };
}

export type WorkflowServiceParams = {
  [K in WorkflowServiceKey]: WorkflowServiceParamsByKey[K];
};

export interface WorkflowServiceRunParamsByKey {
  evaluate: WorkflowServiceParamsByKey["evaluate"];
  build: WorkflowServiceParamsByKey["build"] & {
    _expectedOutput?: string;
  };
  sbom: WorkflowServiceParamsByKey["sbom"];
  activation: WorkflowServiceParamsByKey["activation"];
}

export type WorkflowServiceRunParams<K extends WorkflowServiceKey = WorkflowServiceKey> =
  WorkflowServiceRunParamsByKey[K];

export interface Cable {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  shadow: string;
  connected: boolean;
}

export interface CableGeo {
  cables: Cable[];
  decoCables: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }>;
  w: number;
  h: number;
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
