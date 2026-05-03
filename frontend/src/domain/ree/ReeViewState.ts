import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec, type ReeSpec } from "./ReeSpec";

export type ReeViewState = ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState;

interface ReeModelSplit {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

interface PartialReeModelSplit {
  reeSpec?: Partial<ReeSpec>;
  workspaceSourceState?: Partial<WorkspaceSourceState>;
  artifactStatus?: Partial<ArtifactStatus>;
  evaluationState?: EvaluationState;
}

export function createEmptyReeViewState(): ReeViewState {
  return toReeViewState({ reeSpec: createEmptyReeSpec() });
}

export function splitReeViewState(ree: ReeViewState): ReeModelSplit {
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
    artifactStatus: { runtimeIncluded, downloadableFiles, sealedAt, sealHash },
    evaluationState: { evalLevel },
  };
}

export function splitReeViewPatch(patch: Partial<ReeViewState>): PartialReeModelSplit {
  const split: PartialReeModelSplit = {};
  const has = <K extends keyof ReeViewState>(key: K) => Object.hasOwn(patch, key);
  if (
    has("name") ||
    has("origin_url") ||
    has("source_type") ||
    has("runtime") ||
    has("build_runtime_script") ||
    has("activation_script") ||
    has("sbom") ||
    has("swhid") ||
    has("zenodo_doi") ||
    has("dataverse_doi") ||
    has("repro_level") ||
    has("detected_dependencies") ||
    has("hardware_description")
  ) {
    split.reeSpec = {};
    if (has("name")) split.reeSpec.name = patch.name as ReeSpec["name"];
    if (has("origin_url")) split.reeSpec.origin_url = patch.origin_url as ReeSpec["origin_url"];
    if (has("source_type")) split.reeSpec.source_type = patch.source_type as ReeSpec["source_type"];
    if (has("runtime")) split.reeSpec.runtime = patch.runtime as ReeSpec["runtime"];
    if (has("build_runtime_script"))
      split.reeSpec.build_runtime_script =
        patch.build_runtime_script as ReeSpec["build_runtime_script"];
    if (has("activation_script"))
      split.reeSpec.activation_script = patch.activation_script as ReeSpec["activation_script"];
    if (has("sbom")) split.reeSpec.sbom = patch.sbom as ReeSpec["sbom"];
    if (has("swhid")) split.reeSpec.swhid = patch.swhid as ReeSpec["swhid"];
    if (has("zenodo_doi")) split.reeSpec.zenodo_doi = patch.zenodo_doi as ReeSpec["zenodo_doi"];
    if (has("dataverse_doi"))
      split.reeSpec.dataverse_doi = patch.dataverse_doi as ReeSpec["dataverse_doi"];
    if (has("repro_level")) split.reeSpec.repro_level = patch.repro_level as ReeSpec["repro_level"];
    if (has("detected_dependencies"))
      split.reeSpec.detected_dependencies =
        patch.detected_dependencies as ReeSpec["detected_dependencies"];
    if (has("hardware_description"))
      split.reeSpec.hardware_description =
        patch.hardware_description as ReeSpec["hardware_description"];
  }
  if (
    has("sourceAvailable") ||
    has("sourceIncluded") ||
    has("sourceAcquiredBy") ||
    has("uploadedArchive") ||
    has("sourceSnapshotArchive") ||
    has("sourceSnapshotCapturedAt")
  ) {
    split.workspaceSourceState = {};
    if (has("sourceAvailable")) split.workspaceSourceState.sourceAvailable = patch.sourceAvailable;
    if (has("sourceIncluded")) split.workspaceSourceState.sourceIncluded = patch.sourceIncluded;
    if (has("sourceAcquiredBy"))
      split.workspaceSourceState.sourceAcquiredBy = patch.sourceAcquiredBy;
    if (has("uploadedArchive")) split.workspaceSourceState.uploadedArchive = patch.uploadedArchive;
    if (has("sourceSnapshotArchive"))
      split.workspaceSourceState.sourceSnapshotArchive = patch.sourceSnapshotArchive;
    if (has("sourceSnapshotCapturedAt"))
      split.workspaceSourceState.sourceSnapshotCapturedAt = patch.sourceSnapshotCapturedAt;
  }
  if (has("runtimeIncluded") || has("downloadableFiles") || has("sealedAt") || has("sealHash")) {
    split.artifactStatus = {};
    if (has("runtimeIncluded")) split.artifactStatus.runtimeIncluded = patch.runtimeIncluded;
    if (has("downloadableFiles")) split.artifactStatus.downloadableFiles = patch.downloadableFiles;
    if (has("sealedAt")) split.artifactStatus.sealedAt = patch.sealedAt;
    if (has("sealHash")) split.artifactStatus.sealHash = patch.sealHash;
  }
  if (has("evalLevel")) split.evaluationState = { evalLevel: patch.evalLevel };
  return split;
}

export function toReeViewState(split: Partial<ReeModelSplit> & { reeSpec: ReeSpec }): ReeViewState {
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
