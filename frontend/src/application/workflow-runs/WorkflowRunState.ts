import type {
  ActionStates,
  Badges,
  Timestamps,
  WorkflowLogs,
  WorkflowParams,
} from "../../domain/ree/ReeTypes";
import { initialAutomationStepParams } from "../workflow/workflowCatalog";

export type WorkflowRunStateUpdater<T> = T | ((previous: T) => T);

export interface WorkflowRunState {
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  workflowLogs: WorkflowLogs;
  workflowParams: WorkflowParams;
}

export function resolveWorkflowRunUpdater<T>(previous: T, updater: WorkflowRunStateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialWorkflowRunState(): WorkflowRunState {
  return {
    actionStates: {},
    badges: {},
    timestamps: {},
    workflowLogs: {},
    workflowParams: initialAutomationStepParams(),
  };
}
