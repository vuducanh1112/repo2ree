import type { HBOM, Ree } from "./ReeSpec";
import { splitLegacyReeModel } from "./reeLegacyAdapters";

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

export function toReePatch(ree: Ree): ReePatch {
  const split = splitLegacyReeModel(ree);

  return {
    name: split.reeSpec.name || "",
    origin_url: split.reeSpec.origin_url || "",
    source_type: split.reeSpec.source_type || "",
    runtime: split.reeSpec.runtime || "",
    build_runtime_script: split.reeSpec.build_runtime_script || "",
    activation_script: split.reeSpec.activation_script || "",
    sbom: split.reeSpec.sbom || "",
    swhid: split.reeSpec.swhid || "",
    zenodo_doi: split.reeSpec.zenodo_doi || "",
    dataverse_doi: split.reeSpec.dataverse_doi || "",
    repro_level: split.reeSpec.repro_level || "",
    detected_dependencies: split.reeSpec.detected_dependencies || "",
    hardware_description: split.reeSpec.hardware_description || {},
    _sealedAt: split.artifactStatus.sealedAt || "",
    _sealHash: split.artifactStatus.sealHash || "",
    _evalLevel: split.evaluationState.evalLevel ?? 0,
    _sourceIncluded: !!split.workspaceSourceState.sourceIncluded,
    _sourceAvailable: !!split.workspaceSourceState.sourceAvailable,
    _sourceAcquiredBy: split.workspaceSourceState.sourceAcquiredBy || "",
    _uploadedArchive: split.workspaceSourceState.uploadedArchive || "",
    _sourceSnapshotArchive: split.workspaceSourceState.sourceSnapshotArchive || "",
    _sourceSnapshotCapturedAt: split.workspaceSourceState.sourceSnapshotCapturedAt || "",
    _runtimeIncluded: !!split.artifactStatus.runtimeIncluded,
    _downloadableFiles: split.artifactStatus.downloadableFiles || [],
  };
}
