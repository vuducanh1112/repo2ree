import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import { PAGE } from "../../../../shell/ui/app-shell/state/pages";
import { Ic } from "../../../shared/components/Icon";
import {
  C,
  F,
  S_ACTION_BUTTON_BASE,
  S_FIELD_STACK_GAP_14,
  S_SECTION_LABEL,
  S_TEXT_ITALIC_11,
} from "../../../theme/theme";
import { FieldRow, FieldSection } from "../../components/fieldTips";
import {
  assemblyStatusBadgeStyle,
  assemblyStatusCardStyle,
  assemblyStatusIconWrapStyle,
  assemblyStatusKeyStyle,
  assemblyStatusValueStyle,
  RUNTIME_STATUS_BADGE_STYLE,
} from "../../components/statusUiStyles";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function SbomRuntimeInputSection(props: {
  rt: string | null;
  isTb: boolean | null;
  sbomColor: string;
  focusedField: string | null;
  onFocusField: (value: string) => void;
  onGoBuild: () => void;
}) {
  return (
    <FieldSection
      title="Step 1: Runtime Input"
      icon={Ic.cpu()}
      filledCount={props.rt ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="runtime"
        onFocus={() => props.onFocusField("runtime")}
        active={props.focusedField === "runtime"}
      >
        <div style={S_FIELD_STACK_GAP_14}>
          <div style={assemblyStatusCardStyle(!!props.rt, props.sbomColor)}>
            <div style={assemblyStatusIconWrapStyle(!!props.rt, props.sbomColor)}>
              <span style={{ color: props.rt ? props.sbomColor : C.textMuted, display: "flex" }}>
                {props.isTb ? Ic.archive(14) : Ic.cpu(14)}
              </span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={assemblyStatusKeyStyle(!!props.rt, props.sbomColor)}>
                Scan target · ree.runtime
              </div>
              <div style={assemblyStatusValueStyle(!!props.rt, props.sbomColor)}>
                {props.rt || (
                  <span style={S_TEXT_ITALIC_11}>
                    not set — set a runtime in the Build Runtime step first
                  </span>
                )}
              </div>
            </div>
            {props.rt && (
              <span style={assemblyStatusBadgeStyle(props.sbomColor)}>
                {props.isTb ? "TARBALL" : "IMAGE"}
              </span>
            )}
          </div>

          {!props.rt && (
            <button
              type="button"
              onClick={props.onGoBuild}
              style={{
                ...actionBtn({
                  border: `1px solid ${props.sbomColor}40`,
                  borderRadius: 6,
                  padding: "5px 10px",
                  fontSize: 12,
                  color: props.sbomColor,
                  background: `${props.sbomColor}12`,
                }),
                width: "fit-content",
                display: "flex",
                alignItems: "center",
                gap: 6,
                cursor: "pointer",
              }}
            >
              {Ic.chevR(12)} Go to Build Runtime
            </button>
          )}
        </div>
      </FieldRow>
    </FieldSection>
  );
}

export function SbomProducedSection(props: {
  sbomColor: string;
  hasSbom: boolean;
  sbomNode: FileTreeNode | null;
  sbomUnavailable: boolean;
  sbomTooLargeForPreview: boolean;
  sbomPreviewText: string;
  pkgCount: number | null;
  reeDraft: ReeEditorViewModel;
  focusedField: string | null;
  onFocusField: (value: string) => void;
}) {
  return (
    <FieldSection
      title="Step 2: Produced SBOM"
      icon={Ic.package()}
      filledCount={props.hasSbom ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="sbom"
        onFocus={() => props.onFocusField("sbom")}
        active={props.focusedField === "sbom"}
      >
        <div style={{ ...assemblyStatusCardStyle(props.hasSbom, "#16a34a"), marginBottom: 12 }}>
          <div style={assemblyStatusIconWrapStyle(props.hasSbom, "#16a34a")}>
            <span style={{ color: props.hasSbom ? "#16a34a" : C.textMuted, display: "flex" }}>
              {Ic.package(14)}
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={assemblyStatusKeyStyle(props.hasSbom, "#16a34a")}>ree.sbom</div>
            <div style={assemblyStatusValueStyle(props.hasSbom, "#15803d")}>
              {props.hasSbom ? (
                props.reeDraft.sbom
              ) : (
                <span style={S_TEXT_ITALIC_11}>not set — click Generate SBOM</span>
              )}
            </div>
          </div>
          {props.hasSbom && <span style={RUNTIME_STATUS_BADGE_STYLE}>SET</span>}
        </div>

        {props.hasSbom ? (
          (() => {
            if (!props.sbomNode)
              return (
                <div style={{ color: C.textMuted }}>
                  SBOM file was set but is not present in files.
                </div>
              );
            if (props.sbomUnavailable)
              return (
                <div style={{ color: C.textMuted }}>
                  SBOM file is present but too large to inline in memory. Use the Files page to
                  inspect/download it.
                </div>
              );
            return (
              <div>
                <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>SBOM Preview</div>
                <div
                  style={{
                    border: `1px solid ${props.sbomColor}20`,
                    borderRadius: 10,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "10px 14px",
                      background: `${props.sbomColor}08`,
                      borderBottom: `1px solid ${props.sbomColor}20`,
                    }}
                  >
                    <span style={{ color: props.sbomColor, display: "flex" }}>{Ic.file(13)}</span>
                    <span
                      style={{
                        fontSize: 13,
                        fontFamily: F.mono,
                        fontWeight: 700,
                        color: props.sbomColor,
                        flex: 1,
                      }}
                    >
                      {props.reeDraft.sbom}
                    </span>
                    {props.pkgCount !== null && (
                      <span
                        style={{
                          fontSize: 11,
                          fontFamily: F.sans,
                          color: props.sbomColor,
                          background: `${props.sbomColor}15`,
                          border: `1px solid ${props.sbomColor}30`,
                          borderRadius: 10,
                          padding: "1px 8px",
                        }}
                      >
                        {props.pkgCount} package{props.pkgCount !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <div
                    style={{
                      background: "#0d1117",
                      padding: "14px 16px",
                      maxHeight: 340,
                      overflowY: "auto",
                    }}
                  >
                    <pre
                      style={{
                        margin: 0,
                        fontSize: 11,
                        fontFamily: F.mono,
                        color: "#7ee787",
                        lineHeight: 1.6,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                      }}
                    >
                      {props.sbomPreviewText}
                    </pre>
                  </div>
                </div>
                {props.sbomTooLargeForPreview && (
                  <div style={{ marginTop: 8, fontSize: 11, color: C.textMuted }}>
                    Preview truncated to keep the UI responsive.
                  </div>
                )}
              </div>
            );
          })()
        ) : (
          <div style={{ color: C.textMuted }}>No SBOM generated yet.</div>
        )}
      </FieldRow>
    </FieldSection>
  );
}

export function goToBuild(onGo: (key: typeof PAGE.BUILD) => void) {
  onGo(PAGE.BUILD);
}
