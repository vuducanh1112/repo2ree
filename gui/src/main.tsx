import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { APP_ROUTE } from "./core/app-shell/pages";
import App from "./shell/app/App";
import { reportUiError } from "./shell/app/bootstrap/uiErrorReporter";
import { ErrorBoundary } from "./shell/ui/errors/ErrorBoundary";
import { ApplicationErrorFallback } from "./shell/ui/errors/ErrorFallback";

const container = document.getElementById("root");
if (!container) throw new Error("Root element not found");

createRoot(container).render(
  <React.StrictMode>
    <BrowserRouter>
      <ErrorBoundary
        scope="application"
        reportError={reportUiError}
        fallback={({ retry }) => (
          <ApplicationErrorFallback
            onRetry={retry}
            onReturnHome={() => window.location.assign(APP_ROUTE.ROOT)}
            onReload={() => window.location.reload()}
          />
        )}
      >
        <App reportError={reportUiError} />
      </ErrorBoundary>
    </BrowserRouter>
  </React.StrictMode>,
);
