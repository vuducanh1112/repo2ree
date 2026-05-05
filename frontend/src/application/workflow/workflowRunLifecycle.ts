import { runExecutionLifecycle } from "../ree-assembly/assemblyRunLifecycle";

export function runWorkflowLifecycle(args: {
  startWorkflowRun: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
  request: {
    key: string;
    scriptKey: string;
    params: Record<string, string | boolean | number | null | undefined>;
  };
  pollRun: (runId: string, onUpdate?: (update: unknown) => void) => Promise<unknown>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: unknown) => void;
}) {
  return runExecutionLifecycle({
    startExecutionRun: args.startWorkflowRun,
    request: args.request,
    pollRun: args.pollRun,
    onRunStarted: args.onRunStarted,
    onRunFinished: args.onRunFinished,
    onUpdateLogs: args.onUpdateLogs,
  } as Parameters<typeof runExecutionLifecycle>[0]);
}
