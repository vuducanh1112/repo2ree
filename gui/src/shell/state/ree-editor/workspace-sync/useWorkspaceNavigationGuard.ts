import { useCallback, useEffect, useRef } from "react";
import { useBeforeUnload, useBlocker } from "react-router";

interface WorkspaceNavigationGuardOptions {
  shouldBlock: boolean;
  flush: () => Promise<void>;
  /** Told when the draft could not be saved and the exit went ahead anyway. */
  onFlushFailed?: (error: unknown) => void;
}

/**
 * Hold route navigation until the current REE draft is durable. Browser-level
 * exits cannot await a PATCH, so they receive the platform's unsaved-work
 * confirmation instead.
 */
export function useWorkspaceNavigationGuard({
  shouldBlock,
  flush,
  onFlushFailed,
}: WorkspaceNavigationGuardOptions): void {
  const blocker = useBlocker(shouldBlock);
  const handlingBlockedNavigation = useRef(false);

  useBeforeUnload(
    useCallback(
      (event) => {
        if (!shouldBlock) return;
        event.preventDefault();
        event.returnValue = "";
      },
      [shouldBlock],
    ),
  );

  useEffect(() => {
    if (blocker.state !== "blocked" || handlingBlockedNavigation.current) return;
    handlingBlockedNavigation.current = true;
    // The exit proceeds whether or not the save landed. This guard exists to
    // delay a navigation until the PATCH is durable, not to hold someone in a
    // workspace a failing server will never let them leave: cancelling here
    // dropped the navigation silently and left no way out at all. A failure is
    // announced instead, the header keeps its "Save failed · Retry", and
    // `useBeforeUnload` above still covers a real browser exit.
    void flush()
      .catch((error: unknown) => onFlushFailed?.(error))
      .then(() => blocker.proceed())
      .finally(() => {
        handlingBlockedNavigation.current = false;
      });
  }, [blocker, flush, onFlushFailed]);
}
