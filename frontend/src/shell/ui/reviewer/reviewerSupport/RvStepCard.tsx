import { useEffect, useState } from "react";
import type { LogLine } from "../../../../core/ree/ReeTypes";
import type {
  ReeAssemblyParamValue,
  StepState,
} from "../../../../core/ree-assembly/assemblyStepTypes";
import { C } from "../../theme/theme";
import { RvStepActions } from "./RvStepActions";
import { RvStepHeader } from "./RvStepHeader";
import { RvStepIndicator } from "./RvStepIndicator";
import { RvStepParams } from "./RvStepParams";
import type {
  ReactivationParams,
  ReactivationStep,
  ReactivationStepKey,
} from "./reactivationSteps";

interface RvStepCardProps {
  step: ReactivationStep;
  index: number;
  state: StepState;
  log: LogLine[] | null;
  params: ReactivationParams;
  onSetParam: (
    stepKey: ReactivationStepKey,
    paramKey: string,
    value: ReeAssemblyParamValue,
  ) => void;
  onRun: (key: ReactivationStepKey, params: ReactivationParams) => boolean | Promise<boolean>;
  onCancel?: (key: ReactivationStepKey) => void | Promise<void>;
  isLast: boolean;
  prevDone: boolean;
}

export function RvStepCard({
  step,
  index,
  state,
  log,
  params,
  onSetParam,
  onRun,
  onCancel,
  isLast,
  prevDone,
}: RvStepCardProps) {
  const done = state === "done";
  const running = state === "loading";
  const locked = !prevDone && !done;
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (running) setExpanded(true);
  }, [running]);

  const borderCol = done ? "#22c55e40" : locked ? C.border : `${step.color}30`;
  const bgCol = done ? "#f0fdf4" : locked ? C.bg : `${step.color}08`;

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
      <RvStepIndicator step={step} done={done} running={running} locked={locked} isLast={isLast} />
      <div
        style={{
          flex: 1,
          marginBottom: isLast ? 0 : 14,
          background: bgCol,
          border: `1.5px solid ${borderCol}`,
          borderRadius: 10,
          overflow: "hidden",
          transition: "all 0.25s",
          opacity: locked ? 0.55 : 1,
        }}
      >
        <RvStepHeader
          step={step}
          index={index}
          done={done}
          running={running}
          locked={locked}
          expanded={expanded}
          onToggle={() => !locked && setExpanded((isExpanded) => !isExpanded)}
        />
        {expanded && !locked && (
          <div
            style={{
              padding: "0 14px 14px",
              borderTop: `1px solid ${borderCol}`,
              background: "rgba(255,255,255,0.6)",
            }}
          >
            <RvStepParams step={step} params={params} onSetParam={onSetParam} />
            <RvStepActions
              step={step}
              running={running}
              done={done}
              log={log}
              onRun={() => onRun(step.key, params)}
              onCancel={onCancel ? () => onCancel(step.key) : undefined}
            />
          </div>
        )}
      </div>
    </div>
  );
}
