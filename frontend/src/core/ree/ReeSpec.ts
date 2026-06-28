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
// REE's activation. Each owns a run script — a workspace-relative shell script
// that fully defines how it executes (e.g. its own `docker run …`).
export interface ReeRunnable {
  description: string;
  run_script: string;
  runtime_estimate: string;
  resource_estimates: ExperimentResourceEstimates;
  outputs?: ExpectedOutput[];
}

export interface ReeExperiment extends ReeRunnable {
  name: string;
}

export type ReeActivation = ReeRunnable;

// REE-owned scripts live under a dedicated ree/ directory so their common names
// never clash with a project's own same-named source files in the merged
// workspace. Mirror of RESERVED_* in core reserved_paths.
const SCRIPT_DIR = "ree";
export const RESERVED_BUILD_SCRIPT = `${SCRIPT_DIR}/build_script.sh`;
export const RESERVED_ACTIVATION_SCRIPT = `${SCRIPT_DIR}/activation.sh`;
const EXPERIMENT_SCRIPT_DIR = `${SCRIPT_DIR}/experiments`;

// Derive the reserved per-experiment run-script path from its name. Names are
// already constrained to path-safe characters; spaces become hyphens so the
// path stays tidy.
export function experimentScriptPath(name: string): string {
  const slug = name.trim().replace(/\s+/g, "-") || "experiment";
  return `${EXPERIMENT_SCRIPT_DIR}/${slug}.sh`;
}

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
    run_script: "",
    runtime_estimate: "",
    resource_estimates: createEmptyExperimentResourceEstimates(),
  };
}

export function createEmptyReeActivation(): ReeActivation {
  return {
    description: "",
    run_script: RESERVED_ACTIVATION_SCRIPT,
    runtime_estimate: "",
    resource_estimates: createEmptyExperimentResourceEstimates(),
  };
}

export function createEmptyReeSpec(): ReeSpec {
  return {
    name: "",
    catalog_metadata: createEmptyReeCatalogMetadata(),
    origin_url: "",
    source_type: "",
    runtime: "",
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
