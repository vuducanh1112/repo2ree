import { executeAssemblyRun } from "../ree-assembly/executeAssemblyRun";

interface ExecuteWorkflowStepArgs {
  key: string;
  params: Record<string, string | boolean>;
  ree: unknown;
  level: number;
  workspaceFiles: unknown[];
  workflowRunner: {
    startWorkflowRun: (
      key: string,
      params?: Record<string, string | boolean | number | null | undefined>,
    ) => Promise<{ runId: string }>;
    pollRun: (runId: string, onUpdate?: (update: unknown) => void) => Promise<unknown>;
  };
  workflowStepHandlers: unknown;
  generatedIds: {
    swhid: string;
    zenodoDoi: string;
    dataverseDoi: string;
  };
  executeCommands: (commands: unknown[]) => void;
  refreshWorkspace: () => Promise<{ files: unknown[]; reeFiles?: unknown[]; ree?: unknown }>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export async function executeWorkflowStep(args: ExecuteWorkflowStepArgs) {
  const emitLegacyCommands = (commands: unknown[]) => {
    const legacyCommands = commands.map((command) => {
      if (
        typeof command === "object" &&
        command !== null &&
        "type" in command &&
        (command as { type: string }).type === "setAssemblyRunLog"
      ) {
        return { ...(command as object), type: "setWorkflowRunLog" };
      }
      if (
        typeof command === "object" &&
        command !== null &&
        "type" in command &&
        (command as { type: string }).type === "completeAssemblyRun"
      ) {
        const completion = (command as { completion?: { assemblyRunLog?: unknown } }).completion;
        const legacyCompletion = completion
          ? (() => {
              const { assemblyRunLog, ...rest } = completion as {
                assemblyRunLog?: unknown;
                [key: string]: unknown;
              };
              return { ...rest, workflowLog: assemblyRunLog };
            })()
          : completion;
        return {
          ...(command as object),
          type: "completeWorkflowRun",
          completion: legacyCompletion,
        };
      }
      return command;
    });
    args.executeCommands(legacyCommands);
  };

  return executeAssemblyRun({
    key: args.key,
    params: args.params,
    ree: args.ree,
    level: args.level,
    workspaceFiles: args.workspaceFiles,
    executionRunner: {
      startExecutionRun: args.workflowRunner.startWorkflowRun,
      pollRun: args.workflowRunner.pollRun,
    },
    assemblyCommandPlanners: args.workflowStepHandlers,
    generatedIds: args.generatedIds,
    executeCommands: emitLegacyCommands,
    refreshWorkspace: args.refreshWorkspace,
    onRunStarted: args.onRunStarted,
    onRunFinished: args.onRunFinished,
  } as Parameters<typeof executeAssemblyRun>[0]);
}
