import { APP_PAGE } from "./constants/pages";
import { AppProvider, appActions, appSelectors, useAppContext } from "./context";
import { ExplorerView } from "./features/explorer/ExplorerView";
import { LandingView } from "./features/landing/LandingView";
import { PodOrbitControl } from "./features/reviewer/PodOrbitControl";
import { ReviewerView as ReviewerFeatureView } from "./features/reviewer/ReviewerView";
import { AppRoutes } from "./pages";
import { GLOBAL_CSS } from "./styles/globalCss";
import type { Ree } from "./types";

const DEMO_REE: Ree = {
  name: "genomics-pipeline-v2",
  swhid: "",
  origin_url: "https://github.com/lab/genomics-pipeline",
  source_type: "git",
  detected_dependencies: "",
  repro_level: "",
  runtime: "",
  build_runtime_script: "build_runtime.sh",
  sbom: "",
  activation_script: "activation_test.sh",
  hardware_description: {
    arch: "x86_64",
    memory: "16 GB",
    os: "Debian Bookworm",
    cpu: "Intel Xeon E5-2680",
  },
  _sourceAvailable: false,
  _sourceIncluded: true,
};

const SEALED_DEMO_REE: Ree = {
  ...DEMO_REE,
  swhid: "swh:1:dir:4b825dc642cb6eb9a060e54bf8d69288fbee4904",
  runtime: "runtime.tar.gz",
  sbom: "sbom.spdx.json",
  zenodo_doi: "10.5281/zenodo.1234567",
  _evalLevel: 7,
  _sealedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
  _sealHash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  _sourceIncluded: true,
  _runtimeIncluded: true,
};

function ExplorerRouteView({ onBack }: { onBack: () => void }) {
  return (
    <ExplorerView
      onBack={onBack}
      sealedDemoRee={SEALED_DEMO_REE}
      PodOrbitControl={PodOrbitControl}
    />
  );
}

function ReviewerRouteView({ onBack }: { onBack: () => void }) {
  return (
    <ReviewerFeatureView
      onBack={onBack}
      defaultRee={SEALED_DEMO_REE}
      PodOrbitControl={PodOrbitControl}
    />
  );
}

function AppShell() {
  const { state, dispatch } = useAppContext();
  const appPage = appSelectors.page(state);

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <AppRoutes
        page={appPage}
        onGoLanding={() => dispatch(appActions.setPage(APP_PAGE.LANDING))}
        onGoExplorer={() => dispatch(appActions.setPage(APP_PAGE.EXPLORER))}
        onGoReviewer={() => dispatch(appActions.setPage(APP_PAGE.REVIEWER))}
        LandingView={LandingView}
        ExplorerView={ExplorerRouteView}
        ReviewerView={ReviewerRouteView}
      />
    </>
  );
}

export default function App() {
  return (
    <AppProvider initialExplorerRee={DEMO_REE}>
      <AppShell />
    </AppProvider>
  );
}
