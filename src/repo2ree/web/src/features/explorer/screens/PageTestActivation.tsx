import { useState } from "react";
import { Ic } from "../../../components/Icon";
import { PAGE } from "../../../constants/pages";
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
} from "../../../constants/theme";
import { MOCK_FILES } from "../../../services/dummyWorkspaceService";
import type { ServicePageProps } from "./sharedWorkflowUi";

export function PageTestActivation({
  svc,
  ree,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGoFields,
  badges,
  onGo,
  files,
  onFilesChange,
  onReeChange,
  missing,
  params,
  ui,
}: ServicePageProps) {
  const asLabel = ui.FIELD_META.activation_script?.label || "Activation script";
  const buildColor = svc?.color || "#ef4444";
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const {
    WorkflowPageHeader,
    FieldSection,
    FieldRow,
    FilePicker,
    ServiceActionSection,
    ScriptPanel,
    LogPanel,
    NextStepNudge,
    FieldTipsSidebar,
  } = ui;

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={svc.color}
        icon={Ic.play(18)}
        title={svc?.label || "Test activation"}
        subtitle="Run the activation test script to verify the runtime loads and activates correctly"
        tips={ui.descToTwoTierTips(svc.desc)}
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
                    files={files || MOCK_FILES}
                    placeholder="activation_test.sh"
                    filterFn={(p) => /\.sh$/i.test(p)}
                  />
                </div>
              </div>
            </FieldRow>
          </FieldSection>

          <ServiceActionSection
            color={buildColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Run activation"
            runningLabel="Running…"
            helperText="Runs the activation test script in the runtime environment."
            onRun={() => onRun?.(PAGE.ACTIVATION, params)}
          />

          <div style={S_WORKFLOW_PAGE_SCRIPTS_WRAP}>
            <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Scripts</div>
            {ui.SVC_SCRIPT_FIELDS.activation?.map((sf) => (
              <ScriptPanel
                key={sf.fieldKey}
                scriptKind={sf.scriptKind || null}
                fieldKey={sf.fieldKey}
                files={files || MOCK_FILES}
                onFilesChange={onFilesChange}
                ree={ree}
                onReeChange={onReeChange}
                saveToWorkspaceOnly
              />
            ))}
          </div>

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>Output</div>
            <LogPanel log={log} running={running} />
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
