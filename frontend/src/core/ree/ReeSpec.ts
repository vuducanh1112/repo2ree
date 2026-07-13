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
  coresPerCpu: number;
  threadsPerCore: number;
  architecture: string;
  extraInfo: Record<string, unknown>;
}

export interface GPUDefinition {
  vendor: string;
  quantity: number;
  memoryGb: number;
  interface: string;
  extraInfo: Record<string, unknown>;
}

export interface MemoryDefinition {
  vendor: string;
  quantity: number;
  capacityGb: number;
  memoryType: string;
  speedMtS: number;
  extraInfo: Record<string, unknown>;
}

export interface StorageDefinition {
  vendor: string;
  quantity: number;
  capacityGb: number;
  storageType: string;
  interface: string;
  extraInfo: Record<string, unknown>;
}

export interface NetworkDefinition {
  vendor: string;
  quantity: number;
  bandwidthGbps: number;
  networkType: string;
  interface: string;
  extraInfo: Record<string, unknown>;
}

// ================================================
// Experiment types
// ================================================

export interface ExperimentResourceEstimates {
  cpu: string;
  memory: string;
  gpu: string;
  storage: string;
  network: string;
}

// A Runnable is anything executed inside the runtime: an experiment or the
// REE's activation. Each owns a run script — a workspace-relative shell script
// that fully defines how it executes (e.g. its own `docker run …`) — and an
// optional verify script that checks the run's results afterwards: a plain
// script run from the workspace root after the run script, with nothing
// injected into its environment, whose exit code is the verdict (0 = pass). It
// reads whatever it checks straight from the workspace (to check stdout, the
// run script materializes it to a file). `outputPaths` declares the workspace
// files the run (re)writes — disclosure and drift exclusion, no matcher
// semantics.
export interface ReeRunnable {
  description: string;
  runScript: string;
  verifyScript: string;
  outputPaths: string[];
  runtimeEstimate: string;
  resourceEstimates: ExperimentResourceEstimates;
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
export const RESERVED_ACTIVATION_VERIFY_SCRIPT = `${SCRIPT_DIR}/activation.verify.sh`;
const EXPERIMENT_SCRIPT_DIR = `${SCRIPT_DIR}/experiments`;

// Derive the reserved per-experiment run-script path from its name. Names are
// already constrained to path-safe characters; spaces become hyphens so the
// path stays tidy.
export function experimentScriptPath(name: string): string {
  return `${EXPERIMENT_SCRIPT_DIR}/${experimentSlug(name)}.sh`;
}

// The verify script lives beside the run script under the reserved dir.
export function experimentVerifyScriptPath(name: string): string {
  return `${EXPERIMENT_SCRIPT_DIR}/${experimentSlug(name)}.verify.sh`;
}

function experimentSlug(name: string): string {
  return name.trim().replace(/\s+/g, "-") || "experiment";
}

// ================================================
// REE types
// ================================================

export interface ReeContributor {
  identifier: string;
  name: string;
  affiliationName: string;
  affiliationIdentifier: string;
}

export interface ReeCatalogMetadata {
  description: string;
  version: string;
  website: string;
  keywords: string[];
  contributors: ReeContributor[];
  correspondingAuthorIdentifier: string | null;
}

export interface HBOM {
  cpus: Record<DeviceModel, CPUDefinition>;
  gpus: Record<DeviceModel, GPUDefinition>;
  memory: Record<DeviceModel, MemoryDefinition>;
  storage: Record<DeviceModel, StorageDefinition>;
  network: Record<DeviceModel, NetworkDefinition>;
  extraInfo: Record<string, unknown>;
}

export interface ReeSpec {
  name: string;
  catalogMetadata: ReeCatalogMetadata;
  originUrl: string;
  sourceType: "" | "git" | "hg" | "svn" | "cvs" | "bzr" | "tarball" | "zip";
  /** The concrete commit acquisition resolved the git source to — its reproducibility
   *  receipt, persisted onto the intent and re-fetched at seal. Distinct from the
   *  acquisition *input* ref (the requested commit/branch/tag), which is a transient
   *  form field, not persisted intent. Empty for non-git/upload sources. */
  resolvedRevision: string;
  runtime: string;
  activation: ReeActivation;
  sbom: string;
  swhid: string;
  zenodoDoi?: string;
  dataverseDoi?: string;
  experiments?: ReeExperiment[];
  hardwareDescription: HBOM;
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
    correspondingAuthorIdentifier: null,
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
    runScript: "",
    verifyScript: "",
    outputPaths: [],
    runtimeEstimate: "",
    resourceEstimates: createEmptyExperimentResourceEstimates(),
  };
}

export function createEmptyReeActivation(): ReeActivation {
  return {
    description: "",
    runScript: RESERVED_ACTIVATION_SCRIPT,
    verifyScript: "",
    outputPaths: [],
    runtimeEstimate: "",
    resourceEstimates: createEmptyExperimentResourceEstimates(),
  };
}

/** The source-identity ReeSpec fields, zeroed — one definition every
 *  clear/switch path spreads in, so a newly added identity field can't be
 *  cleared in one path and forgotten in another.
 *
 *  Deliberately excludes `swhid`: unlike these, it is still serialized in the
 *  autosave patch and has a client-side author (the Software Heritage archival
 *  step), so zeroing it locally would clobber a backend-computed value. It is
 *  cleared by the backend on source reset and must be handled there, not here. */
export function clearedSourceIdentityReeSpec(): Pick<
  ReeSpec,
  "originUrl" | "sourceType" | "resolvedRevision"
> {
  return { originUrl: "", sourceType: "", resolvedRevision: "" };
}

export function createEmptyReeSpec(): ReeSpec {
  return {
    name: "",
    catalogMetadata: createEmptyReeCatalogMetadata(),
    originUrl: "",
    sourceType: "",
    resolvedRevision: "",
    runtime: "",
    activation: createEmptyReeActivation(),
    sbom: "",
    swhid: "",
    experiments: [],
    hardwareDescription: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extraInfo: {},
    },
  };
}
