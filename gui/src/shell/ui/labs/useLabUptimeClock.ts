import { useEffect, useState } from "react";

const UPTIME_TICK_MS = 1000;

export function useLabUptimeClock(enabled: boolean): number {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setNowMs(Date.now()), UPTIME_TICK_MS);
    return () => window.clearInterval(id);
  }, [enabled]);

  return nowMs;
}
