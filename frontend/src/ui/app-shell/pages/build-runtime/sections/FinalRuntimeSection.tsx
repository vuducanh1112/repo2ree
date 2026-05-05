import { Ic } from "../../../../shared/components/Icon";
import { S_FIELD_HELP_TEXT_SMALL, S_TEXT_ITALIC_11 } from "../../../../theme/theme";
import { FieldRow, FieldSection } from "../../../components/fieldTips";
import {
  RUNTIME_STATUS_BADGE_STYLE,
  runtimeFieldCardStyle,
  runtimeFieldIconColor,
  runtimeFieldIconWrapStyle,
  runtimeFieldKeyStyle,
  runtimeFieldValueStyle,
  runtimeIncludedLabelStyle,
  runtimeIncludedToggleKnobStyle,
  runtimeIncludedToggleTrackStyle,
  runtimeIncludedValueStyle,
  runtimeIncludedWrapStyle,
  runtimeSizeBadgeStyle,
} from "../../../components/statusUiStyles";
import type { WorkflowPageProps } from "../../sharedWorkflowUi";

interface FinalRuntimeSectionProps {
  includeRuntime: boolean;
  finalRuntime: string;
  finalRuntimeSize: string | null;
  onArtifactStatusChange: WorkflowPageProps["onArtifactStatusChange"];
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}

export function FinalRuntimeSection({
  includeRuntime,
  finalRuntime,
  finalRuntimeSize,
  onArtifactStatusChange,
  focusedField,
  setFocusedField,
}: FinalRuntimeSectionProps) {
  return (
    <FieldSection
      title="Step 4: Final Runtime Field"
      icon={Ic.archive()}
      filledCount={finalRuntime ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="runtime"
        onFocus={() => setFocusedField("runtime")}
        active={focusedField === "runtime"}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={runtimeFieldCardStyle(!!finalRuntime)}>
            <div style={runtimeFieldIconWrapStyle(!!finalRuntime)}>
              <span style={{ color: runtimeFieldIconColor(!!finalRuntime), display: "flex" }}>
                {Ic.archive(14)}
              </span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={runtimeFieldKeyStyle(!!finalRuntime)}>ree.runtime</div>
              <div style={runtimeFieldValueStyle(!!finalRuntime)}>
                {finalRuntime || (
                  <span style={S_TEXT_ITALIC_11}>not set yet — run build or set manually</span>
                )}
              </div>
            </div>
            {finalRuntimeSize && (
              <span style={runtimeSizeBadgeStyle(!!finalRuntime)}>{finalRuntimeSize}</span>
            )}
            {finalRuntime && (
              <div style={runtimeIncludedWrapStyle(!!finalRuntime)}>
                <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                  <div style={runtimeIncludedLabelStyle(includeRuntime)}>Included</div>
                  <div style={runtimeIncludedValueStyle(includeRuntime)}>
                    {includeRuntime ? "Yes" : "No"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    onArtifactStatusChange?.((current) => ({
                      ...current,
                      runtimeIncluded: !includeRuntime,
                    }))
                  }
                  style={runtimeIncludedToggleTrackStyle(includeRuntime)}
                >
                  <span style={runtimeIncludedToggleKnobStyle(includeRuntime)} />
                </button>
              </div>
            )}
            {finalRuntime && <span style={RUNTIME_STATUS_BADGE_STYLE}>FINAL</span>}
          </div>
          <div style={S_FIELD_HELP_TEXT_SMALL}>
            {finalRuntime
              ? includeRuntime
                ? "Runtime will be bundled in the REE archive."
                : "Runtime will not be bundled in the REE archive."
              : "Set a runtime value first."}
          </div>
        </div>
      </FieldRow>
    </FieldSection>
  );
}
