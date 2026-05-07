import { Ic } from "../../../../shared/components/Icon";
import {
  C,
  S_FIELD_HELP_TEXT_SMALL,
  S_FIELD_LABEL_TEXT_SM,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FLEX_ROW_CENTER_GAP_6,
  S_TEXT_ITALIC_11,
} from "../../../../theme/theme";
import { FieldRow, FieldSection } from "../../../components/fieldTips";
import { FilePicker } from "../../../components/scriptAndFile";
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
import type { AssemblyPageProps } from "../../sharedAssemblyUi";

interface RuntimeCollectSectionProps {
  finalRuntime: string;
  finalRuntimeSize: string | null;
  includeRuntime: boolean;
  files: AssemblyPageProps["workspaceFiles"];
  onRuntimeChange: (path: string) => void;
  onArtifactStatusChange: AssemblyPageProps["onArtifactStatusChange"];
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}

export function RuntimeCollectSection({
  finalRuntime,
  finalRuntimeSize,
  includeRuntime,
  files,
  onRuntimeChange,
  onArtifactStatusChange,
  focusedField,
  setFocusedField,
}: RuntimeCollectSectionProps) {
  const filledCount = finalRuntime ? 1 : 0;

  return (
    <FieldSection
      title="Step 2: Collect Runtime"
      icon={Ic.archive()}
      filledCount={filledCount}
      totalCount={1}
    >
      <FieldRow
        fieldKey="runtime"
        onFocus={() => setFocusedField("runtime")}
        active={focusedField === "runtime"}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={S_FLEX_ROW_CENTER_GAP_6}>
            <span style={S_FIELD_LABEL_TEXT_SM}>Runtime tarball</span>
            <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
          </div>
          <div style={S_FIELD_HELP_TEXT_SMALL}>Pick the tarball produced by the build script.</div>
          <FilePicker
            value={finalRuntime}
            onChange={onRuntimeChange}
            files={files || []}
            placeholder="runtime.tar.gz"
            onFocus={() => setFocusedField("runtime")}
          />

          <div
            style={{
              marginTop: 4,
              paddingTop: 12,
              borderTop: `1px solid ${C.border}`,
            }}
          >
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
                    <span style={S_TEXT_ITALIC_11}>
                      not set yet — run build then collect runtime
                    </span>
                  )}
                </div>
              </div>
              {finalRuntimeSize && (
                <span style={runtimeSizeBadgeStyle(!!finalRuntime)}>{finalRuntimeSize}</span>
              )}
              {finalRuntime && (
                <div style={runtimeIncludedWrapStyle(true)}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                    <div style={runtimeIncludedLabelStyle(includeRuntime)}>Included</div>
                    <div style={runtimeIncludedValueStyle(includeRuntime)}>
                      {includeRuntime ? "Yes" : "No"}
                    </div>
                  </div>
                  <button
                    type="button"
                    aria-label="Toggle runtime included"
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
            <div style={{ ...S_FIELD_HELP_TEXT_SMALL, marginTop: 6 }}>
              {finalRuntime
                ? includeRuntime
                  ? "Runtime will be bundled in the REE archive."
                  : "Runtime will not be bundled in the REE archive."
                : "Set a runtime value first."}
            </div>
          </div>
        </div>
      </FieldRow>
    </FieldSection>
  );
}
