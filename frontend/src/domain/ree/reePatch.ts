import type { HBOM, Ree } from "./ReeSpec";

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
  return {
    name: ree.name || "",
    origin_url: ree.origin_url || "",
    source_type: ree.source_type || "",
    runtime: ree.runtime || "",
    build_runtime_script: ree.build_runtime_script || "",
    activation_script: ree.activation_script || "",
    sbom: ree.sbom || "",
    swhid: ree.swhid || "",
    zenodo_doi: ree.zenodo_doi || "",
    dataverse_doi: ree.dataverse_doi || "",
    repro_level: ree.repro_level || "",
    detected_dependencies: ree.detected_dependencies || "",
    hardware_description: ree.hardware_description || {},
    _sealedAt: ree._sealedAt || "",
    _sealHash: ree._sealHash || "",
    _evalLevel: ree._evalLevel ?? 0,
    _sourceIncluded: !!ree._sourceIncluded,
    _sourceAvailable: !!ree._sourceAvailable,
    _sourceAcquiredBy: ree._sourceAcquiredBy || "",
    _uploadedArchive: ree._uploadedArchive || "",
    _sourceSnapshotArchive: ree._sourceSnapshotArchive || "",
    _sourceSnapshotCapturedAt: ree._sourceSnapshotCapturedAt || "",
    _runtimeIncluded: !!ree._runtimeIncluded,
    _downloadableFiles: ree._downloadableFiles || [],
  };
}
