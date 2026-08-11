import type { ReeSpec } from "../ree/ReeSpec";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";

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
  /** What the step's earned-outcome chip says once its run has succeeded. */
  outcomeLabel: string;
  desc: string;
  params: ReeStepParam[];
}

export interface ToastState {
  message: string;
  type: "info" | "success" | "error";
}

export type ArchiveRepoKey = "swh" | "zenodo" | "dataverse";

export interface ArchiveRepo {
  key: ArchiveRepoKey;
  label: string;
  shortLabel: string;
  url: string;
  desc: string;
  idLabel: string;
  idPlaceholder: string;
  params: ReeStepParam[];
  requires: ReeStepRequirement[];
}
