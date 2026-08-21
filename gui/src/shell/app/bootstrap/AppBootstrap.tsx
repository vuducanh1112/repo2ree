import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "../../ui/theme/index.css";
import type { UiErrorReporter } from "../../ui/errors/ErrorBoundary";
import { AppRoutes } from "../../ui/routes";

export function AppBootstrap({ reportError }: { reportError: UiErrorReporter }) {
  return <AppRoutes reportError={reportError} />;
}
