import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec, type ReeDraftViewModel, type ReeSpec } from "./ReeSpec";

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

export function createEmptyReeDraftViewModel(): ReeDraftViewModel {
  return toReeDraftViewModel({
    reeSpec: createEmptyReeSpec(),
  });
}

export function splitReeDraftViewModel(ree: ReeDraftViewModel): ReeModelSplit {
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
    sourceAvailable,
    sourceIncluded,
    sourceAcquiredBy,
    uploadedArchive,
    sourceSnapshotArchive,
    sourceSnapshotCapturedAt,
    runtimeIncluded,
    downloadableFiles,
    sealedAt,
    sealHash,
    evalLevel,
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
      sourceAvailable,
      sourceIncluded,
      sourceAcquiredBy,
      uploadedArchive,
      sourceSnapshotArchive,
      sourceSnapshotCapturedAt,
    },
    artifactStatus: {
      runtimeIncluded,
      downloadableFiles,
      sealedAt,
      sealHash,
    },
    evaluationState: {
      evalLevel,
    },
  };
}

export function splitReePatch(patch: Partial<ReeDraftViewModel>): PartialReeModelSplit {
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
    hasOwn("sourceAvailable") ||
    hasOwn("sourceIncluded") ||
    hasOwn("sourceAcquiredBy") ||
    hasOwn("uploadedArchive") ||
    hasOwn("sourceSnapshotArchive") ||
    hasOwn("sourceSnapshotCapturedAt")
  ) {
    split.workspaceSourceState = {};
    if (hasOwn("sourceAvailable"))
      split.workspaceSourceState.sourceAvailable = patch.sourceAvailable;
    if (hasOwn("sourceIncluded")) split.workspaceSourceState.sourceIncluded = patch.sourceIncluded;
    if (hasOwn("sourceAcquiredBy"))
      split.workspaceSourceState.sourceAcquiredBy = patch.sourceAcquiredBy;
    if (hasOwn("uploadedArchive"))
      split.workspaceSourceState.uploadedArchive = patch.uploadedArchive;
    if (hasOwn("sourceSnapshotArchive"))
      split.workspaceSourceState.sourceSnapshotArchive = patch.sourceSnapshotArchive;
    if (hasOwn("sourceSnapshotCapturedAt"))
      split.workspaceSourceState.sourceSnapshotCapturedAt = patch.sourceSnapshotCapturedAt;
  }

  if (
    hasOwn("runtimeIncluded") ||
    hasOwn("downloadableFiles") ||
    hasOwn("sealedAt") ||
    hasOwn("sealHash")
  ) {
    split.artifactStatus = {};
    if (hasOwn("runtimeIncluded")) split.artifactStatus.runtimeIncluded = patch.runtimeIncluded;
    if (hasOwn("downloadableFiles"))
      split.artifactStatus.downloadableFiles = patch.downloadableFiles;
    if (hasOwn("sealedAt")) split.artifactStatus.sealedAt = patch.sealedAt;
    if (hasOwn("sealHash")) split.artifactStatus.sealHash = patch.sealHash;
  }

  if (hasOwn("evalLevel")) {
    split.evaluationState = {
      evalLevel: patch.evalLevel,
    };
  }

  return split;
}

export function toReeDraftViewModel(
  split: Partial<ReeModelSplit> & { reeSpec: ReeSpec },
): ReeDraftViewModel {
  return {
    ...split.reeSpec,
    sourceAvailable: split.workspaceSourceState?.sourceAvailable ?? false,
    sourceIncluded: split.workspaceSourceState?.sourceIncluded ?? false,
    sourceAcquiredBy: split.workspaceSourceState?.sourceAcquiredBy,
    uploadedArchive: split.workspaceSourceState?.uploadedArchive,
    sourceSnapshotArchive: split.workspaceSourceState?.sourceSnapshotArchive,
    sourceSnapshotCapturedAt: split.workspaceSourceState?.sourceSnapshotCapturedAt,
    runtimeIncluded: split.artifactStatus?.runtimeIncluded ?? false,
    downloadableFiles: split.artifactStatus?.downloadableFiles ?? [],
    sealedAt: split.artifactStatus?.sealedAt,
    sealHash: split.artifactStatus?.sealHash,
    evalLevel: split.evaluationState?.evalLevel ?? 0,
  };
}
