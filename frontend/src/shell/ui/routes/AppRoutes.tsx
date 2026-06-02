import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { ApiClientProvider } from "../../data/apiRuntime";
import { mapReviewDetailToReeEditorViewModel } from "../../data/reviews/mapping";
import { useReviewQuery } from "../../data/reviews/queries";
import { AppShellView } from "../app-shell/AppShellView";
import { APP_ROUTE } from "../app-shell/state/pages";
import { LandingView } from "../landing/LandingView";
import { PodOrbitControl } from "../reviewer/PodOrbitControl";
import { ReviewerView } from "../reviewer/ReviewerView";

function ReviewerRouteView({ onBack }: { onBack: () => void }) {
  const location = useLocation();
  const reviewId = new URLSearchParams(location.search).get("reviewId") || undefined;
  const reviewQuery = useReviewQuery(reviewId);
  const reviewDetail = reviewQuery.data;

  if (reviewQuery.isPending) {
    return <div style={{ padding: 24 }}>Loading review…</div>;
  }

  if (reviewQuery.error) {
    return (
      <div style={{ padding: 24, color: "#b91c1c" }}>
        {reviewQuery.error.message || "Failed to load review"}
      </div>
    );
  }

  return (
    <ReviewerView
      reviewId={reviewId}
      ree={reviewDetail ? mapReviewDetailToReeEditorViewModel(reviewDetail) : undefined}
      reviewFiles={(reviewDetail?.files || []).map((file) => ({
        path: file.path,
        size: file.size,
      }))}
      reviewWorkspaceFiles={(reviewDetail?.workspaceFiles || []).map((file) => ({
        path: file.path,
        size: file.size,
      }))}
      onBack={onBack}
      PodOrbitControl={PodOrbitControl}
    />
  );
}

function WorkspaceRoute({ onBack }: { onBack: () => void }) {
  const [searchParams] = useSearchParams();
  const reeId = searchParams.get("reeId") || undefined;

  return (
    <ApiClientProvider reeId={reeId} key={reeId ?? "new"}>
      <AppShellView onBack={onBack} PodOrbitControl={PodOrbitControl} />
    </ApiClientProvider>
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
        element={<WorkspaceRoute onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route
        path={APP_ROUTE.REVIEWER}
        element={<ReviewerRouteView onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route path="*" element={<Navigate to={APP_ROUTE.ROOT} replace />} />
    </Routes>
  );
}
