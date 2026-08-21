import { useCallback, useEffect, useRef } from "react";
import { useBeforeUnload, useBlocker } from "react-router";

interface WorkspaceNavigationGuardOptions {
  shouldBlock: boolean;
  flush: () => Promise<void>;
}

/**
 * Hold route navigation until the current REE draft is durable. Browser-level
 * exits cannot await a PATCH, so they receive the platform's unsaved-work
 * confirmation instead.
 */
export function useWorkspaceNavigationGuard({
  shouldBlock,
  flush,
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
    void flush()
      .then(() => blocker.proceed())
      .catch(() => blocker.reset())
      .finally(() => {
        handlingBlockedNavigation.current = false;
      });
  }, [blocker, flush]);
}
