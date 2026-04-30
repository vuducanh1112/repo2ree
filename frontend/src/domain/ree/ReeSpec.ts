import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";

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
  origin_url: string;
  source_type: "" | "git" | "hg" | "svn" | "cvs" | "bzr" | "tarball" | "zip";
  runtime: string;
  build_runtime_script: string;
  activation_script: string;
  sbom: string;
  swhid: string;
  zenodo_doi?: string;
  dataverse_doi?: string;
  repro_level?: string;
  detected_dependencies?: string;
  hardware_description: HBOM;
}

interface ReeLegacyTransientFields {
  _sourceAvailable?: boolean;
  _sourceIncluded?: boolean;
  _sourceAcquiredBy?: WorkspaceSourceState["sourceAcquiredBy"];
  _uploadedArchive?: string;
  _sourceSnapshotArchive?: string;
  _sourceSnapshotCapturedAt?: string;
  _runtimeIncluded?: boolean;
  _downloadableFiles?: string[];
  _sealedAt?: string;
  _sealHash?: string;
  _evalLevel?: number;
}

export type ReeDraftViewModel = ReeSpec & ReeLegacyTransientFields;

export function createEmptyReeSpec(): ReeSpec {
  return {
    name: "",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
    sbom: "",
    swhid: "",
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
