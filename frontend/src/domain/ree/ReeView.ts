import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec, type ReeSpec } from "./ReeSpec";

export type ReeView = ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState;

export function createDefaultReeView(): ReeView {
  return {
    ...createEmptyReeSpec(),
    sourceAvailable: false,
    sourceIncluded: false,
    runtimeIncluded: false,
    downloadableFiles: [],
    evalLevel: 0,
  };
}
