import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiClient, type ReviewDetailDto, ReviewsApi } from "../api";
import { SEALED_DEMO_REE } from "../app/demoRee";
import { APP_ROUTE } from "../constants/pages";
import { ExplorerView } from "../features/explorer/ExplorerView";
import { LandingView } from "../features/landing/LandingView";
import { PodOrbitControl } from "../features/reviewer/PodOrbitControl";
import { ReviewerView } from "../features/reviewer/ReviewerView";
import type { Ree } from "../types/ree";

function mapReviewDraftToRee(review: ReviewDetailDto): Ree {
  const draft = review.reeDraft || {};
  return {
    name: String(draft.name ?? review.name ?? ""),
    origin_url: String(draft.origin_url ?? ""),
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
    hardware_description: (draft.hardware_description as Record<string, string>) || {},
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

function ReviewerRouteView({ onBack }: { onBack: () => void }) {
  const location = useLocation();
  const [reviewRee, setReviewRee] = useState<Ree | undefined>(undefined);
  const [reviewFiles, setReviewFiles] = useState<Array<{ path: string; size?: number }>>([]);
  const [loadingReview, setLoadingReview] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const reviewId = params.get("reviewId");
    if (!reviewId) {
      setReviewRee(undefined);
      setReviewFiles([]);
      setLoadError("");
      setLoadingReview(false);
      return;
    }

    let canceled = false;
    const fetchReview = async () => {
      setLoadingReview(true);
      setLoadError("");
      try {
        const env =
          (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
        const api = new ReviewsApi(
          new ApiClient({
            baseUrl: env.VITE_API_BASE_URL || "",
          }),
        );
        const detail = await api.getReview(reviewId);
        if (!canceled) {
          setReviewRee(mapReviewDraftToRee(detail));
          setReviewFiles(
            (detail.files || []).map((file) => ({ path: file.path, size: file.size })),
          );
        }
      } catch (error) {
        if (!canceled) {
          setLoadError(error instanceof Error ? error.message : "Failed to load review");
        }
      } finally {
        if (!canceled) {
          setLoadingReview(false);
        }
      }
    };

    void fetchReview();
    return () => {
      canceled = true;
    };
  }, [location.search]);

  if (loadingReview) {
    return <div style={{ padding: 24 }}>Loading review…</div>;
  }

  if (loadError) {
    return <div style={{ padding: 24, color: "#b91c1c" }}>{loadError}</div>;
  }

  return (
    <ReviewerView
      ree={reviewRee}
      reviewFiles={reviewFiles}
      onBack={onBack}
      defaultRee={SEALED_DEMO_REE}
      PodOrbitControl={PodOrbitControl}
    />
  );
}

export function AppRoutes() {
  const navigate = useNavigate();

  return (
    <Routes>
      <Route path={APP_ROUTE.ROOT} element={<LandingView onLoad={(path) => navigate(path)} />} />
      <Route
        path={APP_ROUTE.EXPLORER}
        element={
          <ExplorerView
            onBack={() => navigate(APP_ROUTE.ROOT)}
            sealedDemoRee={SEALED_DEMO_REE}
            PodOrbitControl={PodOrbitControl}
          />
        }
      />
      <Route
        path={APP_ROUTE.REVIEWER}
        element={<ReviewerRouteView onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route path="*" element={<Navigate to={APP_ROUTE.ROOT} replace />} />
    </Routes>
  );
}
