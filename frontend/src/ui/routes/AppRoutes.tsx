import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useWorkspaceRuntime } from "../../app/browser/BrowserRuntime";
import { APP_ROUTE } from "../../application/app-shell/AppShellPages";
import { mapReviewDetailToRee } from "../../application/review/mapReviewDetailToRee";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import { AppShellView } from "../app-shell/AppShellView";
import { LandingView } from "../landing/LandingView";
import { PodOrbitControl } from "../reviewer/PodOrbitControl";
import { ReviewerView } from "../reviewer/ReviewerView";

function ReviewerRouteView({ onBack }: { onBack: () => void }) {
  const location = useLocation();
  const { reviewRepository } = useWorkspaceRuntime();
  const reviewId = new URLSearchParams(location.search).get("reviewId") || undefined;
  const [reviewRee, setReviewRee] = useState<ReeDraftViewModel | undefined>(undefined);
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
        const detail = await reviewRepository.getReview(reviewId);
        if (!canceled) {
          setReviewRee(mapReviewDetailToRee(detail));
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
  }, [reviewId, reviewRepository]);

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
      reviewRepository={reviewRepository}
      PodOrbitControl={PodOrbitControl}
    />
  );
}

export function AppRoutes() {
  const navigate = useNavigate();

  return (
    <Routes>
      <Route path={APP_ROUTE.ROOT} element={<LandingView onLoad={(path) => navigate(path)} />} />
      <Route path="/explorer" element={<Navigate to={APP_ROUTE.WORKSPACE} replace />} />
      <Route
        path={APP_ROUTE.WORKSPACE}
        element={
          <AppShellView onBack={() => navigate(APP_ROUTE.ROOT)} PodOrbitControl={PodOrbitControl} />
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
