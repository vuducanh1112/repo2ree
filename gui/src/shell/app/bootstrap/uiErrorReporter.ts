import type { UiErrorReporter } from "../../ui/errors/ErrorBoundary";

export const reportUiError: UiErrorReporter = ({ scope, error, componentStack }) => {
  if (!import.meta.env.DEV) return;
  // biome-ignore lint/suspicious/noConsole: development is the default local error-reporting sink
  console.error(`[${scope}] Unexpected React failure`, error, componentStack);
};
