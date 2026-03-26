import { APP_PAGE } from "../constants/pages";
import type { AppPage } from "../types";
import { ExplorerPage } from "./ExplorerPage";
import { LandingPage } from "./LandingPage";
import { ReviewerPage } from "./ReviewerPage";

interface AppRoutesProps {
  page: AppPage;
  onGoLanding: () => void;
  onGoExplorer: () => void;
  onGoReviewer: () => void;
  LandingView: React.ComponentType<{ onLoad: (page: AppPage) => void }>;
  ExplorerView: React.ComponentType<{ onBack: () => void }>;
  ReviewerView: React.ComponentType<{ onBack: () => void }>;
}

export function AppRoutes({
  page,
  onGoLanding,
  onGoExplorer,
  onGoReviewer,
  LandingView,
  ExplorerView,
  ReviewerView,
}: AppRoutesProps) {
  if (page === APP_PAGE.LANDING) {
    return (
      <LandingPage
        LandingView={LandingView}
        onLoad={(nextPage) => {
          if (nextPage === APP_PAGE.EXPLORER) {
            onGoExplorer();
            return;
          }
          if (nextPage === APP_PAGE.REVIEWER) {
            onGoReviewer();
            return;
          }
          onGoLanding();
        }}
      />
    );
  }

  if (page === APP_PAGE.EXPLORER) {
    return <ExplorerPage ExplorerView={ExplorerView} onBack={onGoLanding} />;
  }

  return <ReviewerPage ReviewerView={ReviewerView} onBack={onGoLanding} />;
}
