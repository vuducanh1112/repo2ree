import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { SEALED_DEMO_REE } from "../app/demoRee";
import { APP_ROUTE } from "../constants/pages";
import { ExplorerView } from "../features/explorer/ExplorerView";
import { LandingView } from "../features/landing/LandingView";
import { PodOrbitControl } from "../features/reviewer/PodOrbitControl";
import { ReviewerView } from "../features/reviewer/ReviewerView";

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
        element={
          <ReviewerView
            onBack={() => navigate(APP_ROUTE.ROOT)}
            defaultRee={SEALED_DEMO_REE}
            PodOrbitControl={PodOrbitControl}
          />
        }
      />
      <Route path="*" element={<Navigate to={APP_ROUTE.ROOT} replace />} />
    </Routes>
  );
}
