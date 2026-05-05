import { useState } from "react";
import { scanDependencies } from "../../../../application/workflow/workflowDependencyAnalysis";
import { getWorkflowRequirements } from "../../../../application/workflow/workflowPolicies";
import { LEVELS } from "../../../../domain/review/levels";
import {
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import { automationStepIcon } from "../../automationStepIcons";
import { descToTwoTierTips, FieldTipsSidebar } from "../../components/fieldTips";
import { NextStepNudge, RequirementsBanner, WorkflowPageHeader } from "../../components/pageChrome";
import { WorkflowLogSection, WorkflowRunActionSection } from "../../components/workflowRunPanels";
import type { WorkflowPageProps } from "../sharedWorkflowUi";
import { EvaluateDependenciesSection, EvaluateScoreSection } from "./EvaluatePageSections";

export function PageEvaluate({
  workflow,
  workspaceSourceState,
  evaluationState,
  badges,
  workspaceFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onCancel,
  onGo,
  onGoFields,
  missing,
  params,
}: WorkflowPageProps) {
  const files = workspaceFiles;
  const depGroups = scanDependencies(files || []);
  const hasRun = !!log;
  const hasScoreOutput = !!runDone;
  const sourceLoadedInWorkspace = !!workspaceSourceState.sourceAvailable;
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const IC = automationStepIcon(workflow.iconKey);
  const level = Math.min(evaluationState.evalLevel ?? 0, LEVELS.length - 1);
  const completionPct = Math.round((level / (LEVELS.length - 1)) * 100);
  const requirements = getWorkflowRequirements(workflow.key);

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={workflow.color}
        icon={IC(18)}
        title={workflow.label}
        subtitle={workflow.desc}
        tips={descToTwoTierTips(workflow.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          {missing.length > 0 && (
            <RequirementsBanner
              status="missing"
              items={missing}
              onAction={onGoFields}
              actionLabel="← Go to Source Acquisition"
            />
          )}

          {requirements.length > 0 && missing.length === 0 && (
            <RequirementsBanner status="met" items={requirements} />
          )}

          <WorkflowRunActionSection
            color={workflow.color}
            running={running}
            runDone={runDone}
            disabled={running || !sourceLoadedInWorkspace}
            idleLabel="Run"
            runningLabel="Running…"
            helperText={
              sourceLoadedInWorkspace
                ? "Run evaluation with the selected parameters."
                : "Load source into workspace first. Evaluate is enabled only after source download/upload succeeds."
            }
            onCancel={() => onCancel?.(workflow.key)}
            onRun={() => onRun(workflow.key, params)}
          />

          <EvaluateScoreSection
            hasScoreOutput={hasScoreOutput}
            level={level}
            completionPct={completionPct}
            focusedField={focusedField}
            onFocusField={setFocusedField}
            icon={IC(14)}
          />

          <EvaluateDependenciesSection
            hasRun={hasRun}
            depGroups={depGroups}
            files={files}
            focusedField={focusedField}
            onFocusField={setFocusedField}
          />

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <WorkflowLogSection
              log={log}
              running={running}
              titleStyle={{ letterSpacing: 1.3, fontWeight: 600 }}
            />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge stepKey={workflow.key} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["detected_dependencies", "repro_level"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose either detected dependencies or repro level to see Evaluate-specific tips."
        />
      </div>
    </div>
  );
}
