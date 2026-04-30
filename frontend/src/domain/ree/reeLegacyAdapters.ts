import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec, type ReeDraftViewModel, type ReeSpec } from "./ReeSpec";

// Transitional compatibility layer for legacy merged REE shapes.
// Do not add new responsibilities here; migrate callers away from it instead.
interface ReeModelSplit {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

interface PartialReeModelSplit {
  reeSpec?: Partial<ReeSpec>;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
}

export function createEmptyRee(): ReeDraftViewModel {
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
      sourceAvailable: _sourceAvailable,
      sourceIncluded: _sourceIncluded,
      sourceAcquiredBy: _sourceAcquiredBy,
      uploadedArchive: _uploadedArchive,
      sourceSnapshotArchive: _sourceSnapshotArchive,
      sourceSnapshotCapturedAt: _sourceSnapshotCapturedAt,
    },
    artifactStatus: {
      runtimeIncluded: _runtimeIncluded,
      downloadableFiles: _downloadableFiles,
      sealedAt: _sealedAt,
      sealHash: _sealHash,
    },
    evaluationState: {
      evalLevel: _evalLevel,
    },
  };
}

export function splitLegacyReePatch(patch: Partial<ReeDraftViewModel>): PartialReeModelSplit {
  const split: PartialReeModelSplit = {};
  const hasOwn = <K extends keyof ReeDraftViewModel>(key: K) => Object.hasOwn(patch, key);

  if (
    hasOwn("name") ||
    hasOwn("origin_url") ||
    hasOwn("source_type") ||
    hasOwn("runtime") ||
    hasOwn("build_runtime_script") ||
    hasOwn("activation_script") ||
    hasOwn("sbom") ||
    hasOwn("swhid") ||
    hasOwn("zenodo_doi") ||
    hasOwn("dataverse_doi") ||
    hasOwn("repro_level") ||
    hasOwn("detected_dependencies") ||
    hasOwn("hardware_description")
  ) {
    split.reeSpec = {};
    if (hasOwn("name")) split.reeSpec.name = patch.name as ReeSpec["name"];
    if (hasOwn("origin_url")) split.reeSpec.origin_url = patch.origin_url as ReeSpec["origin_url"];
    if (hasOwn("source_type"))
      split.reeSpec.source_type = patch.source_type as ReeSpec["source_type"];
    if (hasOwn("runtime")) split.reeSpec.runtime = patch.runtime as ReeSpec["runtime"];
    if (hasOwn("build_runtime_script"))
      split.reeSpec.build_runtime_script =
        patch.build_runtime_script as ReeSpec["build_runtime_script"];
    if (hasOwn("activation_script"))
      split.reeSpec.activation_script = patch.activation_script as ReeSpec["activation_script"];
    if (hasOwn("sbom")) split.reeSpec.sbom = patch.sbom as ReeSpec["sbom"];
    if (hasOwn("swhid")) split.reeSpec.swhid = patch.swhid as ReeSpec["swhid"];
    if (hasOwn("zenodo_doi")) split.reeSpec.zenodo_doi = patch.zenodo_doi as ReeSpec["zenodo_doi"];
    if (hasOwn("dataverse_doi"))
      split.reeSpec.dataverse_doi = patch.dataverse_doi as ReeSpec["dataverse_doi"];
    if (hasOwn("repro_level"))
      split.reeSpec.repro_level = patch.repro_level as ReeSpec["repro_level"];
    if (hasOwn("detected_dependencies"))
      split.reeSpec.detected_dependencies =
        patch.detected_dependencies as ReeSpec["detected_dependencies"];
    if (hasOwn("hardware_description"))
      split.reeSpec.hardware_description =
        patch.hardware_description as ReeSpec["hardware_description"];
  }

  if (
    hasOwn("_sourceAvailable") ||
    hasOwn("_sourceIncluded") ||
    hasOwn("_sourceAcquiredBy") ||
    hasOwn("_uploadedArchive") ||
    hasOwn("_sourceSnapshotArchive") ||
    hasOwn("_sourceSnapshotCapturedAt")
  ) {
    split.workspaceSourceState = {};
    if (hasOwn("_sourceAvailable"))
      split.workspaceSourceState.sourceAvailable = patch._sourceAvailable;
    if (hasOwn("_sourceIncluded"))
      split.workspaceSourceState.sourceIncluded = patch._sourceIncluded;
    if (hasOwn("_sourceAcquiredBy"))
      split.workspaceSourceState.sourceAcquiredBy = patch._sourceAcquiredBy;
    if (hasOwn("_uploadedArchive"))
      split.workspaceSourceState.uploadedArchive = patch._uploadedArchive;
    if (hasOwn("_sourceSnapshotArchive"))
      split.workspaceSourceState.sourceSnapshotArchive = patch._sourceSnapshotArchive;
    if (hasOwn("_sourceSnapshotCapturedAt"))
      split.workspaceSourceState.sourceSnapshotCapturedAt = patch._sourceSnapshotCapturedAt;
  }

  if (
    hasOwn("_runtimeIncluded") ||
    hasOwn("_downloadableFiles") ||
    hasOwn("_sealedAt") ||
    hasOwn("_sealHash")
  ) {
    split.artifactStatus = {};
    if (hasOwn("_runtimeIncluded")) split.artifactStatus.runtimeIncluded = patch._runtimeIncluded;
    if (hasOwn("_downloadableFiles"))
      split.artifactStatus.downloadableFiles = patch._downloadableFiles;
    if (hasOwn("_sealedAt")) split.artifactStatus.sealedAt = patch._sealedAt;
    if (hasOwn("_sealHash")) split.artifactStatus.sealHash = patch._sealHash;
  }

  if (hasOwn("_evalLevel")) {
    split.evaluationState = {
      evalLevel: patch._evalLevel,
    };
  }

  return split;
}

export function toLegacyReeViewModel(
  split: Partial<ReeModelSplit> & { reeSpec: ReeSpec },
): ReeDraftViewModel {
  return {
    ...split.reeSpec,
    _sourceAvailable: split.workspaceSourceState?.sourceAvailable ?? false,
    _sourceIncluded: split.workspaceSourceState?.sourceIncluded ?? false,
    _sourceAcquiredBy: split.workspaceSourceState?.sourceAcquiredBy,
    _uploadedArchive: split.workspaceSourceState?.uploadedArchive,
    _sourceSnapshotArchive: split.workspaceSourceState?.sourceSnapshotArchive,
    _sourceSnapshotCapturedAt: split.workspaceSourceState?.sourceSnapshotCapturedAt,
    _runtimeIncluded: split.artifactStatus?.runtimeIncluded ?? false,
    _downloadableFiles: split.artifactStatus?.downloadableFiles ?? [],
    _sealedAt: split.artifactStatus?.sealedAt,
    _sealHash: split.artifactStatus?.sealHash,
    _evalLevel: split.evaluationState?.evalLevel ?? 0,
  };
}
