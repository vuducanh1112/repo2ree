// ReeSpec is the persisted specification of a REE (Reusable Execution Environment),
// the product object. Keep this type narrow - only persisted REE fields. Anything
// UI-, runtime-, or session-flavored belongs in the corresponding slice under
// application/.

// ================================================
// Hardware types
// ================================================

export type DeviceModel = string;

export interface CPUDefinition {
  vendor: string;
  quantity: number;
  cores_per_cpu: number;
  threads_per_core: number;
  architecture: string;
  extra_info: Record<string, unknown>;
}

export interface GPUDefinition {
  vendor: string;
  quantity: number;
  memory_gb: number;
  interface: string;
  extra_info: Record<string, unknown>;
}

export interface MemoryDefinition {
  vendor: string;
  quantity: number;
  capacity_gb: number;
  memory_type: string;
  speed_mt_s: number;
  extra_info: Record<string, unknown>;
}

export interface StorageDefinition {
  vendor: string;
  quantity: number;
  capacity_gb: number;
  storage_type: string;
  interface: string;
  extra_info: Record<string, unknown>;
}

export interface NetworkDefinition {
  vendor: string;
  quantity: number;
  bandwidth_gbps: number;
  network_type: string;
  interface: string;
  extra_info: Record<string, unknown>;
}

// ================================================
// Experiment types
// ================================================

export type OutputSource = { kind: "file"; path: string } | { kind: "stdout" } | { kind: "stderr" };

export type OutputMatch =
  | { mode: "sha256"; value: string }
  | { mode: "contains"; value: string }
  | { mode: "regex"; value: string }
  | { mode: "numeric"; value: string; epsilon: number }
  | { mode: "custom"; value: string };

export interface ExpectedOutput {
  source: OutputSource;
  match: OutputMatch;
}

export interface ExperimentResourceEstimates {
  cpu: string;
  memory: string;
  gpu: string;
  storage: string;
  network: string;
}

// A Runnable is anything executed inside the runtime: an experiment or the
// REE's activation. They share the executable contract; activation has no name.
export interface ReeRunnable {
  description: string;
  command: string;
  runtime_estimate: string;
  resource_estimates: ExperimentResourceEstimates;
  outputs?: ExpectedOutput[];
}

export interface ReeExperiment extends ReeRunnable {
  name: string;
}

export type ReeActivation = ReeRunnable;

// How to enter the built runtime artifact — a property of the runtime, shared
// by activation and every experiment. Mirrors the backend EnvEntry union.
export type ContainerEngine = "docker" | "podman" | "apptainer";

export type RuntimeEntry =
  | {
      kind: "container";
      engine: ContainerEngine;
      workdir: string;
      env: Record<string, string>;
      gpus: boolean;
      activate: string;
      enter_script: string;
    }
  | { kind: "local"; activate: string; enter_script: string }
  | {
      kind: "vm";
      cpu: number;
      memory: string;
      ssh_host: string;
      ssh_user: string;
      ssh_key: string;
      activate: string;
      enter_script: string;
    }
  | { kind: "custom"; enter_script: string; activate: string };

export type RuntimeEntryKind = RuntimeEntry["kind"];

// ================================================
// REE types
// ================================================

export interface ReeContributor {
  identifier: string;
  name: string;
  affiliation_name: string;
  affiliation_identifier: string;
}

export interface ReeCatalogMetadata {
  description: string;
  version: string;
  website: string;
  keywords: string[];
  contributors: ReeContributor[];
  corresponding_author_identifier: string | null;
}

export interface HBOM {
  cpus: Record<DeviceModel, CPUDefinition>;
  gpus: Record<DeviceModel, GPUDefinition>;
  memory: Record<DeviceModel, MemoryDefinition>;
  storage: Record<DeviceModel, StorageDefinition>;
  network: Record<DeviceModel, NetworkDefinition>;
  extra_info: Record<string, unknown>;
}

export interface ReeSpec {
  name: string;
  catalog_metadata: ReeCatalogMetadata;
  origin_url: string;
  source_type: "" | "git" | "hg" | "svn" | "cvs" | "bzr" | "tarball" | "zip";
  runtime: string;
  runtime_entry: RuntimeEntry;
  build_runtime_script: string;
  activation: ReeActivation;
  sbom: string;
  swhid: string;
  zenodo_doi?: string;
  dataverse_doi?: string;
  experiments?: ReeExperiment[];
  hardware_description: HBOM;
}

// ================================================
// Factories
// ================================================

export function createEmptyReeCatalogMetadata(): ReeCatalogMetadata {
  return {
    description: "",
    version: "",
    website: "",
    keywords: [],
    contributors: [],
    corresponding_author_identifier: null,
  };
}

export function createEmptyExperimentResourceEstimates(): ExperimentResourceEstimates {
  return {
    cpu: "",
    memory: "",
    gpu: "",
    storage: "",
    network: "",
  };
}

export function createEmptyReeExperiment(): ReeExperiment {
  return {
    name: "",
    description: "",
    command: "",
    runtime_estimate: "",
    resource_estimates: createEmptyExperimentResourceEstimates(),
  };
}

export function createEmptyReeActivation(): ReeActivation {
  return {
    description: "",
    command: "",
    runtime_estimate: "",
    resource_estimates: createEmptyExperimentResourceEstimates(),
  };
}

export function createDefaultRuntimeEntry(
  kind: RuntimeEntryKind,
  prev?: RuntimeEntry,
): RuntimeEntry {
  switch (kind) {
    case "container":
      return {
        kind: "container",
        engine: prev?.kind === "container" ? prev.engine : "docker",
        workdir: "/workspace",
        env: {},
        gpus: false,
        activate: "",
        enter_script: "",
      };
    case "local":
      return {
        kind: "local",
        activate: prev?.kind === "local" ? prev.activate : "",
        enter_script: "",
      };
    case "vm":
      return {
        kind: "vm",
        cpu: 1,
        memory: "4G",
        ssh_host: "",
        ssh_user: "",
        ssh_key: "",
        activate: "",
        enter_script: "",
      };
    case "custom":
      return { kind: "custom", enter_script: "", activate: "" };
  }
}

export function createEmptyRuntimeEntry(): RuntimeEntry {
  return createDefaultRuntimeEntry("container");
}

export function createEmptyReeSpec(): ReeSpec {
  return {
    name: "",
    catalog_metadata: createEmptyReeCatalogMetadata(),
    origin_url: "",
    source_type: "",
    runtime: "",
    runtime_entry: createEmptyRuntimeEntry(),
    build_runtime_script: "",
    activation: createEmptyReeActivation(),
    sbom: "",
    swhid: "",
    experiments: [],
    hardware_description: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extra_info: {},
    },
  };
}
