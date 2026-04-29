import type { ReviewDetailDto, WorkspaceDetailDto } from "../../api";
import type { Ree } from "../../types";
import { normalizeHBOM } from "../../utils/hbom";

function mapDraftToRee(
  reeDraft: Partial<ReviewDetailDto["reeDraft"]>,
  fallbackName: string,
  fallbackOriginUrl = "",
): Ree {
  return {
    name: String(reeDraft.name ?? fallbackName ?? ""),
    origin_url: String(reeDraft.origin_url ?? fallbackOriginUrl ?? ""),
    source_type: (reeDraft.source_type as Ree["source_type"]) || "",
    runtime: String(reeDraft.runtime ?? ""),
    build_runtime_script: String(reeDraft.build_runtime_script ?? ""),
    activation_script: String(reeDraft.activation_script ?? ""),
    sbom: String(reeDraft.sbom ?? ""),
    swhid: String(reeDraft.swhid ?? ""),
    zenodo_doi: reeDraft.zenodo_doi ? String(reeDraft.zenodo_doi) : undefined,
    dataverse_doi: reeDraft.dataverse_doi ? String(reeDraft.dataverse_doi) : undefined,
    repro_level: reeDraft.repro_level ? String(reeDraft.repro_level) : undefined,
    detected_dependencies: reeDraft.detected_dependencies
      ? String(reeDraft.detected_dependencies)
      : undefined,
    hardware_description: normalizeHBOM(reeDraft.hardware_description),
    _evalLevel: Number(reeDraft._evalLevel ?? 0),
    _sealedAt: reeDraft._sealedAt ? String(reeDraft._sealedAt) : undefined,
    _sealHash: reeDraft._sealHash ? String(reeDraft._sealHash) : undefined,
    _sourceAvailable: Boolean(reeDraft._sourceAvailable),
    _sourceIncluded: Boolean(reeDraft._sourceIncluded),
    _sourceAcquiredBy: (reeDraft._sourceAcquiredBy as Ree["_sourceAcquiredBy"]) || undefined,
    _uploadedArchive: reeDraft._uploadedArchive ? String(reeDraft._uploadedArchive) : undefined,
    _sourceSnapshotArchive: reeDraft._sourceSnapshotArchive
      ? String(reeDraft._sourceSnapshotArchive)
      : undefined,
    _sourceSnapshotCapturedAt: reeDraft._sourceSnapshotCapturedAt
      ? String(reeDraft._sourceSnapshotCapturedAt)
      : undefined,
    _runtimeIncluded: Boolean(reeDraft._runtimeIncluded),
    _downloadableFiles: Array.isArray(reeDraft._downloadableFiles)
      ? reeDraft._downloadableFiles.map((item) => String(item))
      : [],
  };
}

export function mapReviewDraftToRee(review: ReviewDetailDto): Ree {
  return mapDraftToRee(review.reeDraft || {}, review.name);
}

export function mapWorkspaceDraftToRee(workspace: WorkspaceDetailDto): Ree {
  return mapDraftToRee(workspace.reeDraft || {}, workspace.name, workspace.externalRef ?? "");
}
