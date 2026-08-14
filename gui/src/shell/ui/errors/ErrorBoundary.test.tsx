import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary, type UiErrorReporter } from "./ErrorBoundary";
import { ApplicationErrorFallback, WorkspaceErrorFallback } from "./ErrorFallback";

function Broken({ fail, children }: { fail: boolean; children?: ReactNode }) {
  if (fail) throw new Error("render failed");
  return children ?? <div>Recovered content</div>;
}

function quietReactErrors() {
  return vi.spyOn(console, "error").mockImplementation(() => undefined);
}

describe("ErrorBoundary", () => {
  it("reports an unexpected render failure and replaces the failed subtree", () => {
    const consoleError = quietReactErrors();
    const reportError = vi.fn<UiErrorReporter>();

    render(
      <ErrorBoundary
        scope="workspace"
        reportError={reportError}
        fallback={() => <div>Workspace fallback</div>}
      >
        <Broken fail />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Workspace fallback")).toBeInTheDocument();
    expect(reportError).toHaveBeenCalledWith(
      expect.objectContaining({
        scope: "workspace",
        error: expect.objectContaining({ message: "render failed" }),
        componentStack: expect.stringContaining("Broken"),
      }),
    );
    consoleError.mockRestore();
  });

  it("remounts the failed subtree when the user retries", () => {
    const consoleError = quietReactErrors();
    let fail = true;
    function TransientFailure() {
      return <Broken fail={fail} />;
    }

    render(
      <ErrorBoundary
        scope="application"
        reportError={vi.fn()}
        fallback={({ retry }) => (
          <button
            type="button"
            onClick={() => {
              fail = false;
              retry();
            }}
          >
            Retry
          </button>
        )}
      >
        <TransientFailure />
      </ErrorBoundary>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(screen.getByText("Recovered content")).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it("clears a failure when its recovery context changes", () => {
    const consoleError = quietReactErrors();
    const reportError = vi.fn();
    const view = render(
      <ErrorBoundary
        scope="workspace"
        resetKey="ree-one"
        reportError={reportError}
        fallback={() => <div>Workspace fallback</div>}
      >
        <Broken fail />
      </ErrorBoundary>,
    );

    view.rerender(
      <ErrorBoundary
        scope="workspace"
        resetKey="ree-two"
        reportError={reportError}
        fallback={() => <div>Workspace fallback</div>}
      >
        <Broken fail={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Recovered content")).toBeInTheDocument();
    consoleError.mockRestore();
  });
});

describe("error fallbacks", () => {
  it("announces the application failure, focuses its heading, and exposes recovery actions", () => {
    render(
      <ApplicationErrorFallback onRetry={vi.fn()} onReturnHome={vi.fn()} onReload={vi.fn()} />,
    );

    const alert = screen.getByRole("alert");
    const heading = screen.getByRole("heading", {
      level: 1,
      name: "REE Workspace encountered a problem",
    });
    expect(alert).toHaveAccessibleName("REE Workspace encountered a problem");
    expect(heading).toHaveFocus();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Return home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload application" })).toBeInTheDocument();
  });

  it("keeps workspace recovery local and does not offer an application reload", () => {
    const onRetry = vi.fn();
    const onBack = vi.fn();
    render(<WorkspaceErrorFallback onRetry={onRetry} onBack={onBack} />);

    fireEvent.click(screen.getByRole("button", { name: "Try workspace again" }));
    fireEvent.click(screen.getByRole("button", { name: "Return home" }));

    expect(onRetry).toHaveBeenCalledOnce();
    expect(onBack).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Reload application" })).not.toBeInTheDocument();
  });
});
