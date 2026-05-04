import {
  normalizeUiChromePage,
  type SourceOutcomePayload,
  type WorkflowRunCompletionPayload,
} from "../../../application/app-shell/AppShellState";
import type {
  AppShellAction,
  AppShellContextState,
  SliceName,
  SliceShape,
} from "../../../application/app-shell/AppShellTypes";
import { createInitialReeDraftState } from "../../../application/ree-draft/ReeDraftState";
import { resolveUpdater } from "../../../application/state/types";
import { createInitialUiChromeState } from "../../../application/ui-chrome/UiChromeState";
import { createInitialWorkflowRunState } from "../../../application/workflow-runs/WorkflowRunState";
import { enforceSourceOriginRules } from "../../../domain/artifact/sourceOriginRules";
import type { WorkflowParams } from "../../../domain/ree/ReeTypes";
import {
  createEmptyReeViewState,
  type ReeViewState,
  splitReeViewState,
  toReeViewState,
} from "../../../domain/ree/ReeViewState";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";

const sliceNormalizers: {
  [K in SliceName]?: (patch: Partial<SliceShape[K]>, prev: SliceShape[K]) => Partial<SliceShape[K]>;
} = {
  uiChrome: (patch, prev) =>
    patch.page !== undefined
      ? { ...patch, page: normalizeUiChromePage(patch.page, prev.page) }
      : patch,
};

export function createInitialState(
  initialRee: ReeViewState = createEmptyReeViewState(),
): AppShellContextState {
  const normalizedRee = enforceSourceOriginRules(initialRee);
  const split = splitReeViewState(normalizedRee);
  return {
    reeDraft: {
      ...createInitialReeDraftState(normalizedRee),
      workspaceSourceState: split.workspaceSourceState,
      artifactStatus: split.artifactStatus,
    },
    workflowRun: {
      ...createInitialWorkflowRunState(),
      evaluationState: split.evaluationState,
    },
    uiChrome: createInitialUiChromeState(),
  };
}

function buildReeViewFromState(state: AppShellContextState): ReeViewState {
  return toReeViewState({
    reeSpec: state.reeDraft.reeSpec,
    workspaceSourceState: state.reeDraft.workspaceSourceState,
    artifactStatus: state.reeDraft.artifactStatus,
    evaluationState: state.workflowRun.evaluationState,
  });
}

function applyPatch(
  state: AppShellContextState,
  action: Extract<AppShellAction, { type: "patch" }>,
): AppShellContextState {
  const prev = state[action.slice];
  const raw = resolveUpdater(
    prev as Partial<SliceShape[SliceName]>,
    action.updater as (previous: Partial<SliceShape[SliceName]>) => Partial<SliceShape[SliceName]>,
  );
  const normalizer = sliceNormalizers[action.slice] as
    | ((
        patch: Partial<SliceShape[SliceName]>,
        prev: SliceShape[SliceName],
      ) => Partial<SliceShape[SliceName]>)
    | undefined;
  const patch = normalizer ? normalizer(raw, prev as SliceShape[SliceName]) : raw;
  return { ...state, [action.slice]: { ...prev, ...patch } };
}

function applySourceOutcome(
  state: AppShellContextState,
  outcome: SourceOutcomePayload,
): AppShellContextState {
  const { reeDraft, workflowRun } = state;
  return {
    ...state,
    reeDraft: {
      ...reeDraft,
      reeSpec: outcome.reeSpecPatch
        ? { ...reeDraft.reeSpec, ...outcome.reeSpecPatch }
        : reeDraft.reeSpec,
      workspaceSourceState: outcome.workspaceSourceState
        ? { ...reeDraft.workspaceSourceState, ...outcome.workspaceSourceState }
        : reeDraft.workspaceSourceState,
      sourceSnapshotArchiveName: outcome.sourceSnapshotArchiveName,
    },
    workflowRun: {
      ...workflowRun,
      actionStates: outcome.actionState
        ? { ...workflowRun.actionStates, source: outcome.actionState }
        : workflowRun.actionStates,
      badges:
        typeof outcome.badge === "boolean"
          ? { ...workflowRun.badges, source: outcome.badge }
          : workflowRun.badges,
      timestamps: outcome.timestamp
        ? { ...workflowRun.timestamps, source: outcome.timestamp }
        : workflowRun.timestamps,
    },
  };
}

function completeWorkflowRun(
  state: AppShellContextState,
  completion: WorkflowRunCompletionPayload,
): AppShellContextState {
  const { workflowRun } = state;
  return {
    ...state,
    workflowRun: {
      ...workflowRun,
      actionStates: { ...workflowRun.actionStates, [completion.key]: completion.actionState },
      badges: { ...workflowRun.badges, [completion.key]: completion.badge },
      timestamps: { ...workflowRun.timestamps, [completion.key]: completion.timestamp },
    },
  };
}

function resetWorkflowOnSourceChange(
  state: AppShellContextState,
  workflowParams: WorkflowParams,
): AppShellContextState {
  const reset = computeSourceChangeConsequences(
    { ree: buildReeViewFromState(state) },
    workflowParams,
  );
  const split = splitReeViewState(reset.ree);
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      reeSpec: split.reeSpec,
      workspaceSourceState: split.workspaceSourceState,
      artifactStatus: split.artifactStatus,
      sourceSnapshotArchiveName: reset.sourceSnapshotArchiveName,
    },
    workflowRun: {
      ...state.workflowRun,
      evaluationState: split.evaluationState,
      actionStates: reset.actionStates,
      badges: reset.badges,
      timestamps: reset.timestamps,
      workflowParams: reset.workflowParams,
    },
  };
}

export function appShellReducer(
  state: AppShellContextState,
  action: AppShellAction,
): AppShellContextState {
  switch (action.type) {
    case "patch":
      return applyPatch(state, action);
    case "applySourceOutcome":
      return applySourceOutcome(state, action.outcome);
    case "completeWorkflowRun":
      return completeWorkflowRun(state, action.completion);
    case "resetWorkflowOnSourceChange":
      return resetWorkflowOnSourceChange(state, action.workflowParams);
    default:
      return state;
  }
}
