import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

export type ErrorBoundaryScope = "application" | "workspace" | "panel";

export interface UiErrorReport {
  scope: ErrorBoundaryScope;
  error: Error;
  componentStack: string;
}

export type UiErrorReporter = (report: UiErrorReport) => void;

interface ErrorFallbackControls {
  retry: () => void;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  scope: ErrorBoundaryScope;
  reportError: UiErrorReporter;
  fallback: (controls: ErrorFallbackControls) => ReactNode;
  /** A change identifies a new recovery context and clears a previous failure. */
  resetKey?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches unexpected React render and lifecycle failures. Expected operational
 * failures (queries, mutations, and event handlers) stay in their owning UI so
 * users receive a specific, recoverable state instead of a fatal fallback.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.props.reportError({
      scope: this.props.scope,
      error,
      componentStack: info.componentStack ?? "",
    });
  }

  componentDidUpdate(previousProps: ErrorBoundaryProps): void {
    if (this.state.error && previousProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  private retry = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (this.state.error) {
      return this.props.fallback({ retry: this.retry });
    }
    return this.props.children;
  }
}
