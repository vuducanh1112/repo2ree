import type { ReeRun } from "./ReeRun";

export function resolveReeRunTimestamp(run: ReeRun | undefined, fallback: string): string {
  return run?.finishedAt || run?.startedAt || run?.createdAt || fallback;
}
