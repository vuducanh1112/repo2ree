import type {
  ActionStates,
  Badges,
  ReeAssemblyOperationParams,
  Timestamps,
} from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import { initialReeAssemblyOperationParams } from "../ree-assembly/assemblyCatalog";

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
    evaluationState: {
      evalLevel: 0,
    },
    activeRunIds: {},
  };
}
