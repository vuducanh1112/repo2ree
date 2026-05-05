import { createAssemblyRunSession } from "../ree-assembly/assemblyRunSession";

export function createWorkflowRunSession() {
  const session = createAssemblyRunSession();
  return {
    noteRunStarted: session.noteRunStarted,
    noteRunFinished: session.noteRunFinished,
    getActiveRunId: session.getActiveRunId,
    mergeAutomationStepParams: session.mergeAssemblyOperationParams,
    cancelTrackedRun: session.cancelTrackedRun,
  };
}
