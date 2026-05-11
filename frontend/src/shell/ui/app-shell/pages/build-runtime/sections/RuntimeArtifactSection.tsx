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

interface RuntimeArtifactSectionProps {
  finalRuntime: string;
  finalRuntimeSize: string | null;
  runtimePathExists: boolean;
  includeRuntime: boolean;
  files: AssemblyPageProps["workspaceFiles"];
  onRuntimeChange: (path: string) => void;
  onArtifactStatusChange: AssemblyPageProps["onArtifactStatusChange"];
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
}

export function RuntimeArtifactSection({
  finalRuntime,
  finalRuntimeSize,
  runtimePathExists,
  includeRuntime,
  files,
  onRuntimeChange,
  onArtifactStatusChange,
  focusedField,
  setFocusedField,
}: RuntimeArtifactSectionProps) {
  const filledCount = finalRuntime ? 1 : 0;

  return (
    <FieldSection
      title="Step 2: Runtime Artifact"
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
            <span style={S_FIELD_LABEL_TEXT_SM}>Runtime artifact</span>
            <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
          </div>
          <div style={S_FIELD_HELP_TEXT_SMALL}>
            Pick the workspace file that downstream SBOM and activation runs should use.
          </div>
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
                      not set yet — choose a runtime artifact from the workspace
                    </span>
                  )}
                </div>
              </div>
              {finalRuntimeSize && (
                <span style={runtimeSizeBadgeStyle(!!finalRuntime)}>{finalRuntimeSize}</span>
              )}
              {finalRuntime && runtimePathExists && (
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
              {finalRuntime && (
                <span
                  style={{
                    ...RUNTIME_STATUS_BADGE_STYLE,
                    ...(runtimePathExists
                      ? {}
                      : {
                          color: C.error,
                          background: "#fff1f2",
                          border: "1px solid #fecdd3",
                        }),
                  }}
                >
                  {runtimePathExists ? "SELECTED" : "MISSING"}
                </span>
              )}
            </div>
            <div style={{ ...S_FIELD_HELP_TEXT_SMALL, marginTop: 6 }}>
              {finalRuntime
                ? runtimePathExists
                  ? includeRuntime
                    ? "Runtime will be bundled in the REE archive."
                    : "Runtime will not be bundled in the REE archive."
                  : "Selected runtime is not present in the current workspace file tree."
                : "Set a runtime value first."}
            </div>
          </div>
        </div>
      </FieldRow>
    </FieldSection>
  );
}
