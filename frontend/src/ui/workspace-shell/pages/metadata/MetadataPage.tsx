import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import {
  C,
  F,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../theme/theme";
import { FieldRow, FieldSection, FieldTipsSidebar } from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { workflowToneSurfaceStyle } from "../../components/statusUiStyles";
import type { PageMetadataEntryProps } from "../sharedWorkflowUi";

const inp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

export function PageMetadataEntry({
  reeSpec,
  locked,
  badges,
  focusedField,
  onReeChange,
  onLockedChange,
  onGoWorkflow,
  onFocusedFieldChange,
}: PageMetadataEntryProps) {
  const onChange = onReeChange;

  const set = <K extends keyof typeof reeSpec>(k: K, v: (typeof reeSpec)[K]) =>
    onChange({ ...reeSpec, [k]: v } as typeof reeSpec);
  const focus = (key: string) => onFocusedFieldChange(key);

  useFocusScroll(focusedField);

  const identityFilled = [reeSpec.name].filter(Boolean).length;

  return (
    <div style={S_WORKFLOW_PAGE_ROOT}>
      <WorkflowPageHeader
        color="#22c55e"
        icon={Ic.grid(18)}
        title="Provide Metadata"
        subtitle="Capture the project identity that will follow this REE through the workflow"
        tips={[
          "Use a stable, descriptive project name so downstream artifacts stay easy to identify.",
          "Hardware details now live in the dedicated HBOM step right after this one.",
        ]}
        rightAction={
          locked ? (
            <button
              type="button"
              onClick={() => onLockedChange(false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                ...workflowToneSurfaceStyle("warn"),
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontFamily: F.sans,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {Ic.unlock(13)} Unlock fields
            </button>
          ) : null
        }
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_PAGE_MAIN_SCROLL}>
          <div style={S_WORKFLOW_PAGE_MAIN_COL}>
            <FieldSection
              title="Identity"
              icon={Ic.package()}
              filledCount={identityFilled}
              totalCount={1}
            >
              <FieldRow
                fieldKey="name"
                required
                locked={locked}
                onFocus={() => focus("name")}
                active={focusedField === "name"}
              >
                <input
                  disabled={locked}
                  value={reeSpec.name}
                  onChange={(event) => set("name", event.target.value)}
                  onFocus={() => focus("name")}
                  placeholder="my-project-v1.0"
                  style={inp(locked)}
                />
              </FieldRow>
            </FieldSection>

            <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
              <NextStepNudge stepKey="metadata" badges={badges} onGo={onGoWorkflow} />
            </div>
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["name"]}
          focusedField={focusedField}
          onClear={() => onFocusedFieldChange(null)}
        />
      </div>
    </div>
  );
}
