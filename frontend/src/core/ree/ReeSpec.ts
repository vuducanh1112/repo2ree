// ReeSpec is the persisted specification of a REE (Reusable Execution Environment),
// the product object. Keep this type narrow - only persisted REE fields. Anything
// UI-, runtime-, or session-flavored belongs in the corresponding slice under
// application/.
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

export interface ReeExperiment {
  name: string;
  description: string;
  command: string;
}

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
  build_runtime_script: string;
  activation_script: string;
  sbom: string;
  swhid: string;
  zenodo_doi?: string;
  dataverse_doi?: string;
  detected_dependencies?: string;
  experiments?: ReeExperiment[];
  hardware_description: HBOM;
}

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

export function createEmptyReeSpec(): ReeSpec {
  return {
    name: "",
    catalog_metadata: createEmptyReeCatalogMetadata(),
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
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
