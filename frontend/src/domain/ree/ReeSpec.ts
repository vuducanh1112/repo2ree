import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
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

interface ReeModelSplit {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

export type ReeDraftViewModel = ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState;

// Temporary compatibility export for modules that still expect the pre-split model.
export type Ree = ReeDraftViewModel;

export function splitLegacyReeModel(ree: ReeDraftViewModel): ReeModelSplit {
  const {
    name,
    origin_url,
    source_type,
    runtime,
    build_runtime_script,
    activation_script,
    sbom,
    swhid,
    zenodo_doi,
    dataverse_doi,
    repro_level,
    detected_dependencies,
    hardware_description,
    _sourceAvailable,
    _sourceIncluded,
    _sourceAcquiredBy,
    _uploadedArchive,
    _sourceSnapshotArchive,
    _sourceSnapshotCapturedAt,
    _runtimeIncluded,
    _downloadableFiles,
    _sealedAt,
    _sealHash,
    _evalLevel,
  } = ree;

  return {
    reeSpec: {
      name,
      origin_url,
      source_type,
      runtime,
      build_runtime_script,
      activation_script,
      sbom,
      swhid,
      zenodo_doi,
      dataverse_doi,
      repro_level,
      detected_dependencies,
      hardware_description,
    },
    workspaceSourceState: {
      _sourceAvailable,
      _sourceIncluded,
      _sourceAcquiredBy,
      _uploadedArchive,
      _sourceSnapshotArchive,
      _sourceSnapshotCapturedAt,
    },
    artifactStatus: {
      _runtimeIncluded,
      _downloadableFiles,
      _sealedAt,
      _sealHash,
    },
    evaluationState: {
      _evalLevel,
    },
  };
}

export function toLegacyReeViewModel(split: Partial<ReeModelSplit> & { reeSpec: ReeSpec }): Ree {
  return {
    ...split.reeSpec,
    _sourceAvailable: split.workspaceSourceState?._sourceAvailable ?? false,
    _sourceIncluded: split.workspaceSourceState?._sourceIncluded ?? false,
    _sourceAcquiredBy: split.workspaceSourceState?._sourceAcquiredBy,
    _uploadedArchive: split.workspaceSourceState?._uploadedArchive,
    _sourceSnapshotArchive: split.workspaceSourceState?._sourceSnapshotArchive,
    _sourceSnapshotCapturedAt: split.workspaceSourceState?._sourceSnapshotCapturedAt,
    _runtimeIncluded: split.artifactStatus?._runtimeIncluded ?? false,
    _downloadableFiles: split.artifactStatus?._downloadableFiles ?? [],
    _sealedAt: split.artifactStatus?._sealedAt,
    _sealHash: split.artifactStatus?._sealHash,
    _evalLevel: split.evaluationState?._evalLevel ?? 0,
  };
}
