import { normalizeHBOM } from "../../domain/hbom/HbomSummary";
import { type Ree, type ReeSpec, toLegacyReeViewModel } from "../../domain/ree/ReeSpec";
import type { ReviewDetail } from "../ports/ReviewRepository";

interface MapReeDraftToReeOptions {
  reeDraft: Record<string, unknown> | null | undefined;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export function mapReeDraftToRee({
  reeDraft,
  fallbackName,
  fallbackOriginUrl = "",
}: MapReeDraftToReeOptions): Ree {
  const draft = reeDraft || {};
  const reeSpec: ReeSpec = {
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
  };

  return toLegacyReeViewModel({
    reeSpec,
    workspaceSourceState: {
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
    },
    artifactStatus: {
      _runtimeIncluded: Boolean(draft._runtimeIncluded),
      _downloadableFiles: Array.isArray(draft._downloadableFiles)
        ? draft._downloadableFiles.map((item) => String(item))
        : [],
      _sealedAt: draft._sealedAt ? String(draft._sealedAt) : undefined,
      _sealHash: draft._sealHash ? String(draft._sealHash) : undefined,
    },
    evaluationState: {
      _evalLevel: Number(draft._evalLevel ?? 0),
    },
  });
}

export function mapReviewDetailToRee(review: ReviewDetail): Ree {
  return mapReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}
