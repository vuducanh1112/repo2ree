import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { HBOM, ReeSpec } from "./ReeSpec";
import type { ReeViewState } from "./ReeViewState";
import { splitReeViewState } from "./ReeViewState";

interface ReePatch extends Record<string, unknown> {
  name: string;
  origin_url: string;
  source_type: string;
  runtime: string;
  build_runtime_script: string;
  activation_script: string;
  sbom: string;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  repro_level: string;
  detected_dependencies: string;
  hardware_description: HBOM;
  _sealedAt: string;
  _sealHash: string;
  _evalLevel: number;
  _sourceIncluded: boolean;
  _sourceAvailable: boolean;
  _sourceAcquiredBy: string;
  _uploadedArchive: string;
  _sourceSnapshotArchive: string;
  _sourceSnapshotCapturedAt: string;
  _runtimeIncluded: boolean;
  _downloadableFiles: string[];
}

interface ReePatchSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

export function toReePatchFromSlices({
  reeSpec,
  workspaceSourceState,
  artifactStatus,
  evaluationState,
}: ReePatchSlices): ReePatch {
  return {
    name: reeSpec.name || "",
    origin_url: reeSpec.origin_url || "",
    source_type: reeSpec.source_type || "",
    runtime: reeSpec.runtime || "",
    build_runtime_script: reeSpec.build_runtime_script || "",
    activation_script: reeSpec.activation_script || "",
    sbom: reeSpec.sbom || "",
    swhid: reeSpec.swhid || "",
    zenodo_doi: reeSpec.zenodo_doi || "",
    dataverse_doi: reeSpec.dataverse_doi || "",
    repro_level: reeSpec.repro_level || "",
    detected_dependencies: reeSpec.detected_dependencies || "",
    hardware_description: reeSpec.hardware_description || {},
    _sealedAt: artifactStatus.sealedAt || "",
    _sealHash: artifactStatus.sealHash || "",
    _evalLevel: evaluationState.evalLevel ?? 0,
    _sourceIncluded: !!workspaceSourceState.sourceIncluded,
    _sourceAvailable: !!workspaceSourceState.sourceAvailable,
    _sourceAcquiredBy: workspaceSourceState.sourceAcquiredBy || "",
    _uploadedArchive: workspaceSourceState.uploadedArchive || "",
    _sourceSnapshotArchive: workspaceSourceState.sourceSnapshotArchive || "",
    _sourceSnapshotCapturedAt: workspaceSourceState.sourceSnapshotCapturedAt || "",
    _runtimeIncluded: !!artifactStatus.runtimeIncluded,
    _downloadableFiles: artifactStatus.downloadableFiles || [],
  };
}

export function toReePatch(ree: ReeViewState): ReePatch {
  return toReePatchFromSlices(splitReeViewState(ree));
}
