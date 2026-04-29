import type { ReviewDetailDto, WorkspaceDetailDto } from "../../api";
import type { Ree } from "../../types";
import { normalizeHBOM } from "../../utils/hbom";

function mapDraftToRee(
  draft: Partial<ReviewDetailDto["reeDraft"]>,
  fallbackName: string,
  fallbackOriginUrl = "",
): Ree {
  return {
    name: String(draft.name ?? fallbackName ?? ""),
    origin_url: String(draft.origin_url ?? fallbackOriginUrl ?? ""),
    source_type: (draft.source_type as Ree["source_type"]) || "",
    runtime: String(draft.runtime ?? ""),
    build_runtime_script: String(draft.build_runtime_script ?? ""),
    activation_script: String(draft.activation_script ?? ""),
    sbom: String(draft.sbom ?? ""),
    swhid: String(draft.swhid ?? ""),
    zenodo_doi: draft.zenodo_doi ? String(draft.zenodo_doi) : undefined,
    dataverse_doi: draft.dataverse_doi ? String(draft.dataverse_doi) : undefined,
    repro_level: draft.repro_level ? String(draft.repro_level) : undefined,
    detected_dependencies: draft.detected_dependencies
      ? String(draft.detected_dependencies)
      : undefined,
    hardware_description: normalizeHBOM(draft.hardware_description),
    _evalLevel: Number(draft._evalLevel ?? 0),
    _sealedAt: draft._sealedAt ? String(draft._sealedAt) : undefined,
    _sealHash: draft._sealHash ? String(draft._sealHash) : undefined,
    _sourceAvailable: Boolean(draft._sourceAvailable),
    _sourceIncluded: Boolean(draft._sourceIncluded),
    _sourceAcquiredBy: (draft._sourceAcquiredBy as Ree["_sourceAcquiredBy"]) || undefined,
    _uploadedArchive: draft._uploadedArchive ? String(draft._uploadedArchive) : undefined,
    _sourceSnapshotArchive: draft._sourceSnapshotArchive
      ? String(draft._sourceSnapshotArchive)
      : undefined,
    _sourceSnapshotCapturedAt: draft._sourceSnapshotCapturedAt
      ? String(draft._sourceSnapshotCapturedAt)
      : undefined,
    _runtimeIncluded: Boolean(draft._runtimeIncluded),
    _downloadableFiles: Array.isArray(draft._downloadableFiles)
      ? draft._downloadableFiles.map((item) => String(item))
      : [],
  };
}

export function mapReviewDraftToRee(review: ReviewDetailDto): Ree {
  return mapDraftToRee(review.reeDraft || {}, review.name);
}

export function mapWorkspaceDraftToRee(workspace: WorkspaceDetailDto): Ree {
  return mapDraftToRee(workspace.reeDraft || {}, workspace.name, workspace.externalRef ?? "");
}
