import type { ActionStates, Badges, Timestamps, WorkflowParams } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import { initialAutomationStepParams } from "../workflow/workflowCatalog";

export type WorkflowRunStateUpdater<T> = T | ((previous: T) => T);

export interface WorkflowRunState {
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  workflowParams: WorkflowParams;
  evaluationState: EvaluationState;
  activeRunIds: Record<string, string>;
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
    workflowParams: initialAutomationStepParams(),
    evaluationState: {
      evalLevel: 0,
    },
    activeRunIds: {},
  };
}
