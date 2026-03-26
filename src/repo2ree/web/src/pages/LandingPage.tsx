import type { AppPage } from "../types";

interface LandingPageProps {
  LandingView: React.ComponentType<{ onLoad: (page: AppPage) => void }>;
  onLoad: (page: AppPage) => void;
}

export function LandingPage({ LandingView, onLoad }: LandingPageProps) {
  return <LandingView onLoad={onLoad} />;
}
