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

export interface ExperimentResourceEstimates {
  cpu: string;
  memory: string;
  gpu: string;
  storage: string;
  network: string;
}

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

export interface Hbom {
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
  resolvedRevision: string;
  experimentEnvironmentPath: string;
  sbom: string;
  swhid: string;
  experiments?: ReeExperiment[];
  hbom: Hbom;
}

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
    experimentEnvironmentPath: "",
    sbom: "",
    swhid: "",
    experiments: [],
    hbom: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extraInfo: {},
    },
  };
}
