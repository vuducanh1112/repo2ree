import type { ReeStepParams } from "@core/ree/ReeTypes";
import { initialReeStepParams } from "@core/ree-steps/stepCatalog";
import type { StepRunProjection } from "@core/runs/stepRunProjection";

export interface StepRunFormState {
  stepParams: ReeStepParams;
}

export type StepRunState = StepRunFormState & StepRunProjection;

export function createInitialStepRunState(): StepRunFormState {
  return {
    stepParams: initialReeStepParams(),
  };
}
