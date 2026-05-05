import { normalizeHBOM } from "../../domain/hbom/HbomSummary";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { ReeView } from "../../domain/ree/ReeView";
import type { ReviewDetail } from "../../domain/review/ReviewTypes";

interface MapRawReeDraftToReeOptions {
  reeDraft: Record<string, unknown> | null | undefined;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export function mapRawReeDraftToRee({
  reeDraft,
  fallbackName,
  fallbackOriginUrl = "",
}: MapRawReeDraftToReeOptions): ReeView {
  const draft = reeDraft || {};
  const reeSpec: ReeSpec = {
    name: String(draft.name ?? fallbackName ?? ""),
    origin_url: String(draft.origin_url ?? fallbackOriginUrl ?? ""),
    source_type: (draft.source_type as ReeView["source_type"]) || "",
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
  };

  return {
    ...reeSpec,
    sourceAvailable: Boolean(draft._sourceAvailable),
    sourceIncluded: Boolean(draft._sourceIncluded),
    sourceAcquiredBy: (draft._sourceAcquiredBy as ReeView["sourceAcquiredBy"]) || undefined,
    uploadedArchive: draft._uploadedArchive ? String(draft._uploadedArchive) : undefined,
    sourceSnapshotArchive: draft._sourceSnapshotArchive
      ? String(draft._sourceSnapshotArchive)
      : undefined,
    sourceSnapshotCapturedAt: draft._sourceSnapshotCapturedAt
      ? String(draft._sourceSnapshotCapturedAt)
      : undefined,
    runtimeIncluded: Boolean(draft._runtimeIncluded),
    downloadableFiles: Array.isArray(draft._downloadableFiles)
      ? draft._downloadableFiles.map((item) => String(item))
      : [],
    sealedAt: draft._sealedAt ? String(draft._sealedAt) : undefined,
    sealHash: draft._sealHash ? String(draft._sealHash) : undefined,
    evalLevel: Number(draft._evalLevel ?? 0),
  };
}

export function mapReviewDetailToRee(review: ReviewDetail): ReeView {
  return mapRawReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}
