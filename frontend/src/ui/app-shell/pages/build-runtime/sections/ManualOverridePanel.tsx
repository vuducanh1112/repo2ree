import { Ic } from "../../../../shared/components/Icon";
import {
  C,
  hoverBg,
  hoverBorderColor,
  hoverColor,
  S_FLEX_COL_GAP_8,
  S_FLEX_ROW_GAP_8,
  S_SECTION_LABEL_MB12,
  S_TEXT_ITALIC_11,
  S_TEXT_MUTED_11,
  S_WORKFLOW_BUILD_SECTION_WRAP,
} from "../../../../theme/theme";
import { RuntimeField } from "../../../components/sourceRuntime";
import {
  RUNTIME_STATUS_BADGE_STYLE,
  runtimeFieldCardStyle,
  runtimeFieldIconColor,
  runtimeFieldIconWrapStyle,
  runtimeFieldKeyStyle,
  runtimeFieldValueStyle,
  workflowToneSurfaceStyle,
} from "../../../components/statusUiStyles";
import type { WorkflowPageProps } from "../../sharedWorkflowUi";

interface ManualOverridePanelProps {
  showManualOverride: boolean;
  onToggleManualOverride: (next: boolean) => void;
  ree: WorkflowPageProps["ree"];
  onReeChange: WorkflowPageProps["onReeChange"];
  files: WorkflowPageProps["workspaceFiles"];
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}

export function ManualOverridePanel({
  showManualOverride,
  onToggleManualOverride,
  ree,
  onReeChange,
  files,
  focusedField,
  setFocusedField,
}: ManualOverridePanelProps) {
  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const metaRuntime = finalRuntime || null;

  if (!showManualOverride) {
    return (
      <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button
            type="button"
            onClick={() => onToggleManualOverride(true)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "9px 14px",
              borderRadius: 9,
              ...workflowToneSurfaceStyle("warn"),
              borderWidth: "1.5px",
              borderStyle: "solid",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 700,
              boxShadow: "0 1px 2px rgba(146,64,14,0.14)",
              transition: "all 0.14s ease",
            }}
            {...hoverBg("#ffedd5", "#fff7ed")}
            {...hoverBorderColor("#fb923c", "#fdba74")}
          >
            <span
              style={{
                display: "flex",
                width: 18,
                height: 18,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 5,
                background: "#fde68a",
                color: "#92400e",
              }}
            >
              {Ic.x(12)}
            </span>
            Skip building the runtime and manually set it instead. Not Recommended, please try to
            make it work using a build script and running the build.
          </button>
          <div style={S_TEXT_MUTED_11}>
            Only do this if for some reason you cannot build the runtime automatically.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
      <div style={S_SECTION_LABEL_MB12}>Manual Override</div>
      <div style={S_FLEX_COL_GAP_8}>
        <div style={{ fontSize: 11, color: C.textMid, lineHeight: 1.5 }}>
          You chose to skip building — set the runtime field manually. This will override any
          automatic detection.
        </div>
        <div style={runtimeFieldCardStyle(!!metaRuntime)}>
          <div style={runtimeFieldIconWrapStyle(!!metaRuntime)}>
            <span style={{ color: runtimeFieldIconColor(!!metaRuntime), display: "flex" }}>
              {Ic.files(14)}
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={runtimeFieldKeyStyle(!!metaRuntime)}>ree.runtime</div>
            <div style={runtimeFieldValueStyle(!!metaRuntime)}>
              {metaRuntime || <span style={S_TEXT_ITALIC_11}>not set</span>}
            </div>
          </div>
          {metaRuntime && <span style={RUNTIME_STATUS_BADGE_STYLE}>SET</span>}
        </div>
        <RuntimeField
          locked={false}
          ree={ree}
          onChange={onReeChange}
          onFocus={() => setFocusedField("runtime")}
          active={focusedField === "runtime"}
          files={files || []}
        />
        <div style={S_FLEX_ROW_GAP_8}>
          <button
            type="button"
            onClick={() => onToggleManualOverride(false)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "7px 11px",
              borderRadius: 7,
              border: `1.5px solid ${C.borderMid}`,
              background: C.surfaceAlt,
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 700,
              color: C.textMid,
              transition: "all 0.14s ease",
            }}
            {...hoverBg(C.surface, C.surfaceAlt)}
            {...hoverBorderColor(C.accentBorder, C.borderMid)}
            {...hoverColor(C.accent, C.textMid)}
          >
            {Ic.arrowLeft(12)} Back to build flow
          </button>
        </div>
      </div>
    </div>
  );
}
