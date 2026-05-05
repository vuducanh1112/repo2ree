import type { AppShellPage } from "../../../../../application/state/pages";
import type { Badges, LogEntry } from "../../../../../domain/ree/ReeTypes";
import { S_WORKFLOW_PAGE_NUDGE_WRAP } from "../../../../theme/theme";
import { NextStepNudge } from "../../../components/pageChrome";
import {
  WorkflowLogSection,
  WorkflowRunActionSection,
} from "../../../components/workflowRunPanels";

interface HardwareBomRunSectionProps {
  running: boolean;
  runDone: boolean;
  log: LogEntry | null;
  ts?: string | null;
  badges: Badges;
  onRun: () => void;
  onCancel?: () => void;
  onGoWorkflow: (stepKey: AppShellPage) => void;
}

export function HardwareBomRunSection({
  running,
  runDone,
  log,
  ts,
  badges,
  onRun,
  onCancel,
  onGoWorkflow,
}: HardwareBomRunSectionProps) {
  return (
    <>
      <WorkflowRunActionSection
        color="#0f766e"
        running={running}
        runDone={runDone}
        disabled={running}
        idleLabel="Profile This Machine"
        runningLabel="Profiling…"
        doneLabel="Re-profile Machine"
        helperText="Detects local CPU, GPU, memory, storage, and network details, then fills the HBOM table."
        onCancel={onCancel}
        onRun={onRun}
      />

      <WorkflowLogSection
        log={log}
        running={running}
        title={ts ? "Machine profiling logs" : "Profiling logs"}
      />

      <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
        <NextStepNudge stepKey="hbom" badges={badges} onGo={onGoWorkflow} />
      </div>
    </>
  );
}
