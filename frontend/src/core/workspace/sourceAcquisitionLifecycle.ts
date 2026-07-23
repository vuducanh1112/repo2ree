import type { WorkspaceResetPayload } from "../../core/workspace/WorkspaceReset";
import { parseWorkspaceResetPayload } from "../../core/workspace/WorkspaceReset";
import type { ReeRunPollResult, ReeRunUpdate } from "../ree-steps/stepRunLifecycle";
import { runExecutionLifecycle } from "../ree-steps/stepRunLifecycle";

// Once source acquisition actually starts, it is a run like any other, so the
// start/observe/report-once bookkeeping is the shared lifecycle. What is
// specific to source is the branch above it: a request carrying no mode is a
// workspace reset, which never becomes a run at all.

interface SourceExecutionResult {
  runId?: string;
  status: ReeRunPollResult["status"];
}

interface SourceReeRunner {
  resetWorkspaceRequest: (id: string, payload: WorkspaceResetPayload) => Promise<void>;
}

interface SourceExecutionPoller {
  startReeRun: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<{ runId: string }>;
}

interface RunSourceWorkspaceActionArgs {
  reeClient: SourceReeRunner;
  executionRunClient: SourceExecutionPoller;
  reeId: string;
  resetPayload: string;
  runParams: Record<string, string | boolean | number | null | undefined>;
  pollRun: (
    reeId: string,
    runId: string,
    onUpdate?: (update: ReeRunUpdate) => void,
  ) => Promise<ReeRunPollResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string, runId: string) => void;
  onUpdateLogs?: (update: ReeRunUpdate) => void;
}

export async function runSourceWorkspaceAction({
  reeClient,
  executionRunClient,
  reeId,
  resetPayload,
  runParams,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunSourceWorkspaceActionArgs): Promise<SourceExecutionResult> {
  if (!runParams.mode) {
    await reeClient.resetWorkspaceRequest(reeId, parseWorkspaceResetPayload(resetPayload, "git"));
    return { status: "succeeded" };
  }

  return runExecutionLifecycle({
    startReeRun: (scriptKey, params) => executionRunClient.startReeRun(reeId, scriptKey, params),
    request: { key: "source", scriptKey: "source", params: runParams },
    pollRun: (runId, onUpdate) => pollRun(reeId, runId, onUpdate),
    onRunStarted,
    onRunFinished,
    onUpdateLogs,
  });
}
