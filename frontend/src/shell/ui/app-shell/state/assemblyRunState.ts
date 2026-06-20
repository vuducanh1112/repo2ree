import { type EvaluationState, emptyEvaluationState } from "@core/evaluate/EvaluationState";
import type {
  ActionStates,
  Badges,
  ReeAssemblyOperationParams,
  Timestamps,
} from "@core/ree/ReeTypes";
import { initialReeAssemblyOperationParams } from "@core/ree-assembly/assemblyCatalog";

export interface AssemblyRunState {
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  assemblyOperationParams: ReeAssemblyOperationParams;
  evaluationState: EvaluationState;
  activeRunIds: Record<string, string>;
}

export function createInitialAssemblyRunState(): AssemblyRunState {
  return {
    actionStates: {},
    badges: {},
    timestamps: {},
    assemblyOperationParams: initialReeAssemblyOperationParams(),
    evaluationState: emptyEvaluationState(),
    activeRunIds: {},
  };
}
