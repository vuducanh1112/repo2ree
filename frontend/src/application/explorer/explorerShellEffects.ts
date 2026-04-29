import type { ServiceRunCommand } from "./serviceRunCommands";
import type { SourceCommand } from "./sourceCommands";

type ServiceRunHydrationCommand = Extract<ServiceRunCommand, { type: "hydrateWorkspace" }>;
type SourceHydrationCommand = Extract<SourceCommand, { type: "hydrateWorkspace" }>;

export type ExplorerShellEffect =
  | { type: "setActionLoading"; key: string }
  | {
      type: "setServiceLog";
      key: string;
      lines: Extract<ServiceRunCommand, { type: "setServiceLog" }>["lines"];
      ts: string;
    }
  | {
      type: "completeServiceRun";
      completion: Extract<ServiceRunCommand, { type: "completeServiceRun" }>["completion"];
    }
  | {
      type: "hydrateWorkspace";
      virtualFiles:
        | ServiceRunHydrationCommand["virtualFiles"]
        | SourceHydrationCommand["virtualFiles"];
      workspaceReeFiles:
        | NonNullable<ServiceRunHydrationCommand["workspaceReeFiles"]>
        | NonNullable<SourceHydrationCommand["workspaceReeFiles"]>;
      ree: ServiceRunHydrationCommand["ree"] | SourceHydrationCommand["ree"];
    }
  | { type: "persistFile"; path: string; content: string }
  | { type: "patchRee"; patch: Extract<ServiceRunCommand, { type: "patchRee" }>["patch"] }
  | { type: "setLocked"; locked: boolean }
  | {
      type: "resetWorkflowOnSourceChange";
      serviceParams: Extract<
        SourceCommand,
        { type: "resetWorkflowOnSourceChange" }
      >["serviceParams"];
    }
  | {
      type: "applySourceOutcome";
      outcome: Extract<SourceCommand, { type: "applySourceOutcome" }>["outcome"];
    }
  | {
      type: "setSourceLog";
      lines: Extract<SourceCommand, { type: "setSourceLog" }>["lines"];
      ts: Extract<SourceCommand, { type: "setSourceLog" }>["ts"];
    }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function mapServiceRunCommandsToEffects(
  commands: ServiceRunCommand[],
): ExplorerShellEffect[] {
  return commands.map((command) => {
    if (command.type === "persistFile") {
      return {
        type: "persistFile",
        path: command.path,
        content: command.content,
      };
    }
    if (command.type === "toast") {
      return {
        type: "toast",
        message: command.message,
        toastType: command.toastType,
      };
    }
    return command;
  });
}

export function mapSourceCommandsToEffects(commands: SourceCommand[]): ExplorerShellEffect[] {
  return commands.map((command) => {
    if (command.type === "toast") {
      return {
        type: "toast",
        message: command.message,
        toastType: command.toastType,
      };
    }
    if (command.type === "setSourceLoading") {
      return {
        type: "setActionLoading",
        key: "source",
      };
    }
    return command;
  });
}
