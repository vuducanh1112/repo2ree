import type { LogEntry } from "@core/ree/ReeTypes";
import { CollapsibleLogCard } from "@shell/ui/app-shell/components/CollapsibleLogCard";

interface BuildLogCardProps {
  log: LogEntry | null;
  running: boolean;
  ts?: string;
}

export function BuildLogCard({ log, running, ts }: BuildLogCardProps) {
  return <CollapsibleLogCard log={log} running={running} title={ts ? "Build log" : "Build logs"} />;
}
