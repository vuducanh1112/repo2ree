import { APP_ROUTE } from "@core/app-shell/pages";
import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import { Navigate, Route, Routes, useNavigate, useSearchParams } from "react-router-dom";
import { ReeScopeProvider } from "../../data/apiRuntime";
import { AgentsView } from "../agents/AgentsView";
import { LabLocationView } from "../agents/LabLocationView";
import { AppShellView } from "../app-shell/AppShellView";
import { ErrorBoundary, type UiErrorReporter } from "../errors/ErrorBoundary";
import { WorkspaceErrorFallback } from "../errors/ErrorFallback";
import { LandingView } from "../landing/LandingView";
import { ReeIndexView } from "../ree-index/ReeIndexView";

function WorkspaceRoute({
  onBack,
  reportError,
}: {
  onBack: () => void;
  reportError: UiErrorReporter;
}) {
  const [searchParams] = useSearchParams();
  const reeId = searchParams.get("reeId") || undefined;
  const workspaceKey = reeId ?? "new";

  return (
    <ErrorBoundary
      scope="workspace"
      reportError={reportError}
      resetKey={workspaceKey}
      fallback={({ retry }) => <WorkspaceErrorFallback onRetry={retry} onBack={onBack} />}
    >
      <ReeScopeProvider reeId={reeId ?? DEFAULT_REE_ID} key={workspaceKey}>
        <AppShellView onBack={onBack} />
      </ReeScopeProvider>
    </ErrorBoundary>
  );
}

export function AppRoutes({ reportError }: { reportError: UiErrorReporter }) {
  const navigate = useNavigate();

  return (
    <Routes>
      <Route
        path={APP_ROUTE.ROOT}
        element={
          <LandingView
            onLoad={(path) => navigate(path)}
            onViewAgents={() => navigate(APP_ROUTE.AGENTS)}
            onViewReeIndex={() => navigate(APP_ROUTE.REE_INDEX)}
          />
        }
      />
      <Route path="/explorer" element={<Navigate to={APP_ROUTE.WORKSPACE} replace />} />
      <Route
        path={APP_ROUTE.LAB_LOCATION}
        element={<LabLocationView onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route
        path={APP_ROUTE.WORKSPACE}
        element={
          <WorkspaceRoute onBack={() => navigate(APP_ROUTE.ROOT)} reportError={reportError} />
        }
      />
      <Route
        path={APP_ROUTE.AGENTS}
        element={<AgentsView onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route
        path={APP_ROUTE.REE_INDEX}
        element={<ReeIndexView onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route path="*" element={<Navigate to={APP_ROUTE.ROOT} replace />} />
    </Routes>
  );
}
