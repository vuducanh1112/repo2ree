import { useCallback, useEffect, useRef } from "react";
import { useBeforeUnload, useBlocker } from "react-router";

interface WorkspaceNavigationGuardOptions {
  shouldBlock: boolean;
  flush: () => Promise<void>;
  onFlushFailed?: (error: unknown) => void;
}

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
    void flush()
      .catch((error: unknown) => onFlushFailed?.(error))
      .then(() => blocker.proceed())
      .finally(() => {
        handlingBlockedNavigation.current = false;
      });
  }, [blocker, flush, onFlushFailed]);
}
