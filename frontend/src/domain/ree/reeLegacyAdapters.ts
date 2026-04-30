import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec, type Ree, type ReeDraftViewModel, type ReeSpec } from "./ReeSpec";

// Transitional compatibility layer for legacy merged REE shapes.
// Do not add new responsibilities here; migrate callers away from it instead.
interface ReeModelSplit {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

export function createEmptyRee(): Ree {
  return toLegacyReeViewModel({
    reeSpec: createEmptyReeSpec(),
  });
}

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
