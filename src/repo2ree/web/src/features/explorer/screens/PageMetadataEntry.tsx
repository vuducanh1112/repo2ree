import type React from "react";
import { Ic } from "../../../components/Icon";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverColor,
  S_ACTION_BUTTON_BASE,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../constants/theme";
import { useFocusScroll } from "../../../hooks/useFocusScroll";
import { FieldRow, FieldSection, FieldTipsSidebar } from "../components/workflow/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../components/workflow/pageChrome";
import type { PageMetadataEntryProps } from "./sharedWorkflowUi";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

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
  ree,
  locked,
  badges,
  focusedField,
  onReeChange,
  onLockedChange,
  onGoService,
  onFocusedFieldChange,
}: PageMetadataEntryProps) {
  const onChange = onReeChange;

  const set = <K extends keyof typeof ree>(k: K, v: (typeof ree)[K]) =>
    onChange({ ...ree, [k]: v } as typeof ree);
  const focus = (key: string) => onFocusedFieldChange(key);

  useFocusScroll(focusedField);

  const identityFilled = [ree.name].filter(Boolean).length;
  const hardwareFilled = Object.values(ree.hardware_description).filter((v) => v.trim?.()).length;

  return (
    <div style={S_WORKFLOW_PAGE_ROOT}>
      <WorkflowPageHeader
        color="#22c55e"
        icon={Ic.grid(18)}
        title="Provide Metadata"
        subtitle="Capture project identity and hardware context needed for reproducibility"
        tips={[
          "Capture essential project and hardware context for reproducibility.",
          "Use stable, descriptive values so builds can be interpreted and repeated later.",
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
                background: "#fef3c7",
                border: "1px solid #fde68a",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontFamily: F.sans,
                color: "#92400e",
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
                  value={ree.name}
                  onChange={(event) => set("name", event.target.value)}
                  onFocus={() => focus("name")}
                  placeholder="my-project-v1.0"
                  style={inp(locked)}
                />
              </FieldRow>
            </FieldSection>

            <FieldSection
              title="Hardware"
              icon={Ic.chip()}
              subtitle="target machine specification"
              filledCount={hardwareFilled > 0 ? 1 : 0}
              totalCount={1}
            >
              <FieldRow
                fieldKey="hardware_description"
                locked={locked}
                onFocus={() => focus("hardware_description")}
                active={focusedField === "hardware_description"}
              >
                <div
                  style={{ padding: "12px 0", display: "flex", flexDirection: "column", gap: 6 }}
                >
                  {Object.entries(ree.hardware_description).map(([k, v], i) => (
                    <div key={k} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <input
                        disabled={locked}
                        value={k}
                        onChange={(event) => {
                          const ent = Object.entries(ree.hardware_description);
                          ent[i] = [event.target.value, v];
                          onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                        }}
                        placeholder="key"
                        style={{ ...inp(locked, { width: "auto", fontSize: 14 }), flex: "0 0 36%" }}
                      />
                      <span style={{ color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>
                        :
                      </span>
                      <input
                        disabled={locked}
                        value={v}
                        onChange={(event) => {
                          const ent = Object.entries(ree.hardware_description);
                          ent[i] = [k, event.target.value];
                          onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                        }}
                        placeholder="value"
                        style={{ ...inp(locked, { width: "auto", fontSize: 14 }), flex: 1 }}
                      />
                      {!locked && (
                        <button
                          type="button"
                          onClick={() => {
                            const ent = Object.entries(ree.hardware_description).filter(
                              (_, j) => j !== i,
                            );
                            onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            color: C.textMuted,
                            padding: "4px",
                            display: "flex",
                            borderRadius: 5,
                            flexShrink: 0,
                          }}
                          {...hoverColor("#dc2626", C.textMuted)}
                          {...hoverBg("#fef2f2", "transparent")}
                        >
                          {Ic.x()}
                        </button>
                      )}
                    </div>
                  ))}
                  {!locked && (
                    <button
                      type="button"
                      onClick={() => {
                        const ent = [...Object.entries(ree.hardware_description), ["", ""]];
                        onChange({ ...ree, hardware_description: Object.fromEntries(ent) });
                      }}
                      style={{
                        ...actionBtn({
                          border: `1.5px dashed ${C.borderMid}`,
                          padding: "6px 10px",
                          background: "transparent",
                          color: C.textMuted,
                          transition: "border-color 0.14s,color 0.14s",
                        }),
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        cursor: "pointer",
                        marginTop: 4,
                        width: "fit-content",
                      }}
                      {...hoverBorderColor(C.accent, C.borderMid)}
                      {...hoverColor(C.accent, C.textMuted)}
                    >
                      {Ic.plus()} Add field
                    </button>
                  )}
                </div>
              </FieldRow>
            </FieldSection>

            <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
              <NextStepNudge stepKey={"metadata"} badges={badges} onGo={onGoService} />
            </div>
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["name", "hardware_description"]}
          focusedField={focusedField}
          onClear={() => onFocusedFieldChange(null)}
        />
      </div>
    </div>
  );
}
