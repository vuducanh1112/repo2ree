import { APP_ROUTE } from "@core/app-shell/pages";
import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import { lazy, type ReactNode, Suspense } from "react";
import { Navigate, Route, Routes, useNavigate, useSearchParams } from "react-router-dom";
import { ReeScopeProvider } from "../../data/apiRuntime";
import { ErrorBoundary, type UiErrorReporter } from "../errors/ErrorBoundary";
import { WorkspaceErrorFallback } from "../errors/ErrorFallback";
import { LandingView } from "../landing/LandingView";
import styles from "./AppRoutes.module.css";

const LabLocationView = lazy(() =>
  import("../agents/LabLocationView").then(({ LabLocationView: View }) => ({ default: View })),
);
const AgentsView = lazy(() =>
  import("../agents/AgentsView").then(({ AgentsView: View }) => ({ default: View })),
);
const ReeIndexView = lazy(() =>
  import("../ree-index/ReeIndexView").then(({ ReeIndexView: View }) => ({ default: View })),
);
const AppShellView = lazy(() =>
  import("../app-shell/AppShellView").then(({ AppShellView: View }) => ({ default: View })),
);

function DeferredRoute({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <main className={styles.loading} role="status" aria-live="polite">
          <span className={styles.loadingIndicator} aria-hidden />
          <span>Loading view…</span>
        </main>
      }
    >
      {children}
    </Suspense>
  );
}

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
        element={
          <DeferredRoute>
            <LabLocationView onBack={() => navigate(APP_ROUTE.ROOT)} />
          </DeferredRoute>
        }
      />
      <Route
        path={APP_ROUTE.WORKSPACE}
        element={
          <DeferredRoute>
            <WorkspaceRoute onBack={() => navigate(APP_ROUTE.ROOT)} reportError={reportError} />
          </DeferredRoute>
        }
      />
      <Route
        path={APP_ROUTE.AGENTS}
        element={
          <DeferredRoute>
            <AgentsView onBack={() => navigate(APP_ROUTE.ROOT)} />
          </DeferredRoute>
        }
      />
      <Route
        path={APP_ROUTE.REE_INDEX}
        element={
          <DeferredRoute>
            <ReeIndexView onBack={() => navigate(APP_ROUTE.ROOT)} />
          </DeferredRoute>
        }
      />
      <Route path="*" element={<Navigate to={APP_ROUTE.ROOT} replace />} />
    </Routes>
  );
}
