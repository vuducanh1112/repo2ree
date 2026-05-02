import { useState } from "react";
import { PAGE } from "../../../../application/app-shell/AppShellPages";
import { FIELD_META } from "../../../../application/app-shell/fieldMeta";
import { Ic } from "../../../shared/components/Icon";
import {
  S_FIELD_HELP_TEXT_SMALL,
  S_FIELD_LABEL_TEXT_SM,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FIELD_STACK_GAP_5,
  S_FIELD_STACK_GAP_14,
  S_FLEX_ROW_CENTER_GAP_6,
  S_SECTION_LABEL,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_SCRIPTS_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import {
  descToTwoTierTips,
  FieldRow,
  FieldSection,
  FieldTipsSidebar,
} from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { FilePicker, ScriptPanel } from "../../components/scriptAndFile";
import { WorkflowLogSection, WorkflowRunActionSection } from "../../components/workflowRunPanels";
import { SVC_SCRIPT_FIELDS } from "../sharedWorkflowConstants";
import type { WorkflowPageProps } from "../sharedWorkflowUi";

export function PageTestActivation({
  workflow,
  ree,
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
  onReeChange,
  onFilesChange,
  onPersistWorkspaceFile,
}: WorkflowPageProps) {
  const files = workspaceFiles;

  const asLabel = FIELD_META.activation_script?.label || "Activation script";
  const buildColor = workflow?.color || "#ef4444";
  const [focusedField, setFocusedField] = useState<string | null>(null);

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={workflow.color}
        icon={Ic.play(18)}
        title={workflow?.label || "Test activation"}
        subtitle="Run the activation test script to verify the runtime loads and activates correctly"
        tips={descToTwoTierTips(workflow.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          <FieldSection
            title="Fields"
            icon={Ic.play()}
            filledCount={ree.activation_script ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="activation_script"
              onFocus={() => setFocusedField("activation_script")}
              active={focusedField === "activation_script"}
            >
              <div style={S_FIELD_STACK_GAP_14}>
                <div style={S_FIELD_STACK_GAP_5}>
                  <div style={S_FLEX_ROW_CENTER_GAP_6}>
                    <span style={S_FIELD_LABEL_TEXT_SM}>{asLabel}</span>
                    <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
                  </div>
                  <div style={S_FIELD_HELP_TEXT_SMALL}>
                    Shell script that loads the runtime and verifies the environment activates
                    correctly
                  </div>
                  <FilePicker
                    disabled={false}
                    value={ree.activation_script}
                    onChange={(v) => onReeChange?.({ ...ree, activation_script: v })}
                    files={files || []}
                    placeholder="activation_test.sh"
                    filterFn={(p) => /\.sh$/i.test(p)}
                  />
                </div>
              </div>
            </FieldRow>
          </FieldSection>

          <WorkflowRunActionSection
            color={buildColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Run activation"
            runningLabel="Running…"
            helperText="Runs the activation test script in the runtime environment."
            onCancel={() => onCancel?.(workflow.key)}
            onRun={() => onRun(workflow.key, params)}
          />

          <div style={S_WORKFLOW_PAGE_SCRIPTS_WRAP}>
            <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Scripts</div>
            {SVC_SCRIPT_FIELDS.activation?.map((sf) => (
              <ScriptPanel
                key={sf.fieldKey}
                scriptKind={sf.scriptKind || null}
                fieldKey={sf.fieldKey}
                files={files || []}
                onFilesChange={onFilesChange}
                onPersistWorkspaceFile={onPersistWorkspaceFile}
                ree={ree}
                onReeChange={onReeChange}
                saveToWorkspaceOnly
              />
            ))}
          </div>

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <WorkflowLogSection log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge
              stepKey={PAGE.ACTIVATION}
              badges={badges || {}}
              onGo={onGo || (() => {})}
            />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["activation_script", "runtime"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
        />
      </div>
    </div>
  );
}
