import type { ReeStepParams } from "@core/ree/ReeTypes";
import { initialReeStepParams } from "@core/ree-steps/stepCatalog";
import type { StepRunProjection } from "@core/runs/stepRunProjection";

export interface StepRunFormState {
  stepParams: ReeStepParams;
}

/** Backend-run projection plus the few local form values a step page owns. */
export type StepRunState = StepRunFormState & StepRunProjection;

export function createInitialStepRunState(): StepRunFormState {
  return {
    stepParams: initialReeStepParams(),
  };
}
