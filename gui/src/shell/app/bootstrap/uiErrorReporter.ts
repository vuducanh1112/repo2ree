import type { UiErrorReporter } from "../../ui/errors/ErrorBoundary";

/**
 * Browser-side adapter for unexpected UI failures. Production reporting can
 * replace this composition-root adapter without coupling the boundary to a
 * telemetry vendor or moving browser effects into the functional core.
 */
export const reportUiError: UiErrorReporter = ({ scope, error, componentStack }) => {
  if (!import.meta.env.DEV) return;
  // biome-ignore lint/suspicious/noConsole: development is the default local error-reporting sink
  console.error(`[${scope}] Unexpected React failure`, error, componentStack);
};
