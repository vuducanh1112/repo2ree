import { createEmptyReeSpec, type ReeSpec } from "@core/ree/ReeSpec";

export interface ReeIntentState {
  reeSpec: ReeSpec;
}

export function createInitialReeIntentState(input: { reeSpec?: ReeSpec } = {}): ReeIntentState {
  return {
    reeSpec: input.reeSpec ?? createEmptyReeSpec(),
  };
}
