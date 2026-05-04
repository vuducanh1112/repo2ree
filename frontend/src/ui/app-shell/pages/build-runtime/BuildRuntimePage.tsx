import { useMemo, useState } from "react";
import type { AutomationStepRunParams } from "../../../../application/workflow/WorkflowTypes";
import { Ic } from "../../../shared/components/Icon";
import {
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import { descToTwoTierTips, FieldTipsSidebar } from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { WorkflowLogSection } from "../../components/workflowRunPanels";
import { findFileByPath } from "../sharedWorkflowHelpers";
import type { WorkflowPageProps } from "../sharedWorkflowUi";
import { deriveRuntimeFileSize } from "./buildRuntimeHelpers";
import { BuildActionPanel } from "./sections/BuildActionPanel";
import { BuildScriptSection } from "./sections/BuildScriptSection";
import { ExpectedOutputSection } from "./sections/ExpectedOutputSection";
import { FinalRuntimeSection } from "./sections/FinalRuntimeSection";
import { ManualOverridePanel } from "./sections/ManualOverridePanel";

export function PageBuildRuntime({
  workflow,
  ree,
  artifactStatus,
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
  setParam,
  onReeChange,
  onFilesChange,
  onPersistWorkspaceFile,
}: WorkflowPageProps) {
  const files = workspaceFiles;

  const [expectedOutput, setExpectedOutput] = useState(() =>
    ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "",
  );
  const buildParams: AutomationStepRunParams<"build"> = {
    ...(params as AutomationStepRunParams<"build">),
    build_runtime_script_path: ree.build_runtime_script,
    produced_runtime_path: expectedOutput,
    _expectedOutput: expectedOutput,
  };
  const [showManualOverride, setShowManualOverride] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const buildColor = workflow.color;
  const imageColor = "#0891b2";
  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const includeRuntime = !!artifactStatus.runtimeIncluded && !!finalRuntime;
  const finalRuntimeFile = useMemo(() => {
    if (!finalRuntime) return null;
    return (
      findFileByPath(files || [], finalRuntime) ||
      findFileByPath(files || [], finalRuntime.split("/").pop() || "")
    );
  }, [files, finalRuntime]);
  const finalRuntimeSize = useMemo(
    () => deriveRuntimeFileSize(finalRuntimeFile),
    [finalRuntimeFile],
  );

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={workflow.color}
        icon={Ic.cpu(18)}
        title={workflow.label}
        subtitle={workflow.desc}
        tips={descToTwoTierTips(workflow.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        timestampPrefix="Last built"
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          <BuildScriptSection
            workflow={workflow}
            ree={ree}
            files={files}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
            onReeChange={onReeChange}
            onFilesChange={onFilesChange}
            onPersistWorkspaceFile={onPersistWorkspaceFile}
            onTemplateSuggestedOutput={setExpectedOutput}
          />

          <ExpectedOutputSection
            workflow={workflow}
            expectedOutput={expectedOutput}
            setExpectedOutput={setExpectedOutput}
            params={params}
            setParam={setParam}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
          />

          <BuildActionPanel
            buildColor={buildColor}
            running={running}
            runDone={runDone}
            missing={missing}
            onRun={onRun}
            onCancel={onCancel}
            workflowKey={workflow.key}
            buildParams={buildParams}
            expectedOutput={expectedOutput}
            ree={ree}
            imageColor={imageColor}
            files={files}
          />

          <ManualOverridePanel
            showManualOverride={showManualOverride}
            onToggleManualOverride={setShowManualOverride}
            ree={ree}
            onReeChange={onReeChange}
            files={files}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
          />

          <FinalRuntimeSection
            ree={ree}
            includeRuntime={includeRuntime}
            finalRuntime={finalRuntime}
            finalRuntimeSize={finalRuntimeSize}
            onReeChange={onReeChange}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
          />

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <WorkflowLogSection log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge stepKey={workflow.key} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["build_runtime_script", "runtime"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
        />
      </div>
    </div>
  );
}
