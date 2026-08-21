import { type EvaluationState, emptyEvaluationState } from "@core/evaluate/EvaluationState";
import type { ActionStates, Badges, ReeStepParams, Timestamps } from "@core/ree/ReeTypes";
import { initialReeStepParams } from "@core/ree-steps/stepCatalog";

export interface StepRunState {
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  stepParams: ReeStepParams;
  evaluationState: EvaluationState;
  activeRunIds: Record<string, string>;
}

export function createInitialStepRunState(): StepRunState {
  return {
    actionStates: {},
    badges: {},
    timestamps: {},
    stepParams: initialReeStepParams(),
    evaluationState: emptyEvaluationState(),
    activeRunIds: {},
  };
}
