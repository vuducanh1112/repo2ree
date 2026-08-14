import { useEffect, useState } from "react";

const UPTIME_TICK_MS = 1000;

/**
 * Supplies one shared wall-clock reading for every agent rendered by a view.
 * It stays dormant until there is an uptime label to update.
 */
export function useAgentUptimeClock(enabled: boolean): number {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setNowMs(Date.now()), UPTIME_TICK_MS);
    return () => window.clearInterval(id);
  }, [enabled]);

  return nowMs;
}
