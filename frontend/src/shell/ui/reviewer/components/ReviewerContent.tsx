import type { ReeFile } from "../../../../core/ree/ReeTypes";
import type {
  ReeAssemblyParamValue,
  StepState,
} from "../../../../core/ree-assembly/assemblyStepTypes";
import type { StandingMeta } from "../../../../core/review/axes";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { PageFiles } from "../../app-shell/pages/files/FilesPage";
import { C } from "../../theme/theme";
import {
  REACTIVATION_STEPS,
  type ReactivationParams,
  type ReactivationStepKey,
  RvStepCard,
  RvVerdictBanner,
} from "../reviewerSupport";

interface ReviewerContentProps {
  reviewerPage: "review" | "files";
  evaluation: EvaluationState;
  levelMeta: StandingMeta;
  stepStates: Partial<Record<ReactivationStepKey, StepState>>;
  stepLogs: Partial<Record<ReactivationStepKey, import("../../../../core/ree/ReeTypes").LogLine[]>>;
  stepParams: Record<ReactivationStepKey, ReactivationParams>;
  allDone: boolean;
  isRunningAll: boolean;
  runAll: () => void;
  setParam: (stepKey: ReactivationStepKey, paramKey: string, value: ReeAssemblyParamValue) => void;
  runStep: (key: ReactivationStepKey, params: ReactivationParams) => boolean | Promise<boolean>;
  cancelStep: (key: ReactivationStepKey) => void | Promise<void>;
  reviewReeFiles: ReeFile[];
  PodOrbitControl: React.ComponentType<{
    evaluation: EvaluationState;
    levelMeta: StandingMeta;
    stepStates: Record<string, StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

export function ReviewerContent({
  reviewerPage,
  evaluation,
  levelMeta,
  stepStates,
  stepLogs,
  stepParams,
  allDone,
  isRunningAll,
  runAll,
  setParam,
  runStep,
  cancelStep,
  reviewReeFiles,
  PodOrbitControl,
}: ReviewerContentProps) {
  return (
    <main
      style={{
        flex: 1,
        overflowY: "auto",
        minWidth: 0,
        background: `linear-gradient(180deg, ${levelMeta.bg}50 0%, ${C.bg} 320px)`,
      }}
    >
      {reviewerPage === "review" ? (
        <>
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              borderBottom: `1px solid ${C.border}`,
              paddingBottom: 28,
            }}
          >
            <PodOrbitControl
              evaluation={evaluation}
              levelMeta={levelMeta}
              stepStates={stepStates}
              allDone={allDone}
              isRunningAll={isRunningAll}
              onRunAll={runAll}
            />
          </div>
          <div style={{ padding: "20px 28px" }}>
            {allDone && (
              <div style={{ marginBottom: 20 }}>
                <RvVerdictBanner allDone={allDone} />
              </div>
            )}
            <div style={{ maxWidth: 660 }}>
              {REACTIVATION_STEPS.map((step, index) => {
                const prevDone =
                  index === 0 || stepStates[REACTIVATION_STEPS[index - 1].key] === "done";
                return (
                  <RvStepCard
                    key={step.key}
                    step={step}
                    index={index}
                    state={stepStates[step.key] || "idle"}
                    log={stepLogs[step.key] || null}
                    params={stepParams[step.key]}
                    onSetParam={setParam}
                    onRun={runStep}
                    onCancel={cancelStep}
                    isLast={index === REACTIVATION_STEPS.length - 1}
                    prevDone={prevDone}
                  />
                );
              })}
            </div>
          </div>
        </>
      ) : (
        <div style={{ padding: "20px 28px" }}>
          <div style={{ maxWidth: 980 }}>
            <PageFiles reeFiles={reviewReeFiles} />
          </div>
        </div>
      )}
    </main>
  );
}
