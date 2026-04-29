import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiClient, ReviewsApi } from "../api";
import { SEALED_DEMO_REE } from "../app/demoRee";
import { APP_ROUTE } from "../constants/pages";
import { ExplorerView } from "../features/explorer/ExplorerView";
import { LandingView } from "../features/landing/LandingView";
import { PodOrbitControl } from "../features/reviewer/PodOrbitControl";
import { ReviewerView } from "../features/reviewer/ReviewerView";
import { mapReviewDraftToRee } from "../infra/api/reeMappers";
import type { Ree } from "../types/ree";

function ReviewerRouteView({ onBack }: { onBack: () => void }) {
  const location = useLocation();
  const reviewId = new URLSearchParams(location.search).get("reviewId") || undefined;
  const [reviewRee, setReviewRee] = useState<Ree | undefined>(undefined);
  const [reviewFiles, setReviewFiles] = useState<Array<{ path: string; size?: number }>>([]);
  const [reviewWorkspaceFiles, setReviewWorkspaceFiles] = useState<
    Array<{ path: string; size?: number }>
  >([]);
  const [loadingReview, setLoadingReview] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!reviewId) {
      setReviewRee(undefined);
      setReviewFiles([]);
      setReviewWorkspaceFiles([]);
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
          setReviewWorkspaceFiles(
            (detail.workspaceFiles || []).map((file) => ({ path: file.path, size: file.size })),
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
  }, [reviewId]);

  if (loadingReview) {
    return <div style={{ padding: 24 }}>Loading review…</div>;
  }

  if (loadError) {
    return <div style={{ padding: 24, color: "#b91c1c" }}>{loadError}</div>;
  }

  return (
    <ReviewerView
      reviewId={reviewId}
      ree={reviewRee}
      reviewFiles={reviewFiles}
      reviewWorkspaceFiles={reviewWorkspaceFiles}
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
