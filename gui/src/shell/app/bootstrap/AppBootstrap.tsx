import "../../ui/theme/index.css";
import type { UiErrorReporter } from "../../ui/errors/ErrorBoundary";
import { AppRoutes } from "../../ui/routes";

export function AppBootstrap({ reportError }: { reportError: UiErrorReporter }) {
  return <AppRoutes reportError={reportError} />;
}
