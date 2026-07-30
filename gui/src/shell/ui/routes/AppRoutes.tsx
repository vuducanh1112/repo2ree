import { APP_ROUTE } from "@core/app-shell/pages";
import { Navigate, Route, Routes, useNavigate, useSearchParams } from "react-router-dom";
import { ApiClientProvider } from "../../data/apiRuntime";
import { AgentsView } from "../agents/AgentsView";
import { LabLocationView } from "../agents/LabLocationView";
import { AppShellView } from "../app-shell/AppShellView";
import { LandingView } from "../landing/LandingView";
import { ReeIndexView } from "../ree-index/ReeIndexView";

function WorkspaceRoute({ onBack }: { onBack: () => void }) {
  const [searchParams] = useSearchParams();
  const reeId = searchParams.get("reeId") || undefined;

  return (
    <ApiClientProvider reeId={reeId} key={reeId ?? "new"}>
      <AppShellView onBack={onBack} />
    </ApiClientProvider>
  );
}

export function AppRoutes() {
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
          // Agent selection is global (pre-REE); the provider just supplies reeApi.
          <ApiClientProvider>
            <LabLocationView onBack={() => navigate(APP_ROUTE.ROOT)} />
          </ApiClientProvider>
        }
      />
      <Route
        path={APP_ROUTE.WORKSPACE}
        element={<WorkspaceRoute onBack={() => navigate(APP_ROUTE.ROOT)} />}
      />
      <Route
        path={APP_ROUTE.AGENTS}
        element={
          // Agents are global, not REE-scoped; the provider just supplies reeApi.
          <ApiClientProvider>
            <AgentsView onBack={() => navigate(APP_ROUTE.ROOT)} />
          </ApiClientProvider>
        }
      />
      <Route
        path={APP_ROUTE.REE_INDEX}
        element={
          // The index spans every REE this node has sealed, so like agents it
          // is global and the provider only supplies reeApi.
          <ApiClientProvider>
            <ReeIndexView onBack={() => navigate(APP_ROUTE.ROOT)} />
          </ApiClientProvider>
        }
      />
      <Route path="*" element={<Navigate to={APP_ROUTE.ROOT} replace />} />
    </Routes>
  );
}
