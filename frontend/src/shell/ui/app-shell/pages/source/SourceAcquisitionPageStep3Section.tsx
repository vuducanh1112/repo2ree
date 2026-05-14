import { Ic } from "../../../shared/components/Icon";
import { Toggle } from "../../../shared/components/Toggle";
import { lgColors, lgContentCard, lgGlassButton, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import type { AppShellPage } from "../../state/pages";
import { PAGE } from "../../state/pages";
import type { SourceAcquisitionPageProps } from "../sharedAssemblyUi";

interface Step3Props {
  step3Ready: boolean;
  sourceIncludedEffective: boolean;
  sourceIncludedLocked: boolean;
  sourceFromUpload: boolean;
  sourceInWorkspace: boolean;
  acquisitionNarrative: string;
  workspaceSourceState: SourceAcquisitionPageProps["workspaceSourceState"];
  locked: boolean;
  focus: (key: string) => void;
  onToggleSourceIncluded: () => void;
  onGoAssemblyPage: (page: AppShellPage) => void;
  onRemoveWorkspaceSource: () => void;
}

export function SourceStep3Section(props: Step3Props) {
  return (
    <div style={lgContentCard()}>
      <div style={{ ...lgStyles.label, marginBottom: 10 }}>Workspace Snapshot</div>

      {props.step3Ready ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: 13,
                fontFamily: F.sans,
                color: lgColors.text,
              }}
            >
              Include snapshot in REE
            </span>
            <Toggle
              on={props.sourceIncludedEffective}
              disabled={props.sourceIncludedLocked}
              color="#0ea5e9"
              onChange={props.onToggleSourceIncluded}
              title={
                props.sourceFromUpload
                  ? "Uploads are always included in final REE to preserve source."
                  : !props.sourceInWorkspace
                    ? "Load source into workspace first"
                    : props.sourceIncludedEffective
                      ? "Source will be included in final REE"
                      : "Source will be excluded from final REE"
              }
              width={36}
              height={18}
              knobSize={14}
            />
            {props.sourceFromUpload && (
              <span style={lgStyles.helper}>
                Uploaded source is always included to preserve reproducibility.
              </span>
            )}
          </div>

          <div style={{ fontSize: 13, color: lgColors.textMid, fontFamily: F.sans }}>
            {props.acquisitionNarrative}
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => {
                props.focus("sourceAvailable");
                props.onGoAssemblyPage(PAGE.FILES);
              }}
              style={{
                ...lgGlassButton(),
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {Ic.files(12)} Browse workspace files
            </button>
            {props.workspaceSourceState.sourceAvailable && (
              <button
                type="button"
                disabled={props.locked}
                onClick={() => {
                  props.focus("sourceAvailable");
                  props.onRemoveWorkspaceSource();
                }}
                style={{
                  padding: "9px 14px",
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 700,
                  fontFamily: F.sans,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  border: "1px solid rgba(251, 113, 133, 0.4)",
                  background: props.locked
                    ? "rgba(241, 245, 249, 0.72)"
                    : "rgba(255, 241, 242, 0.82)",
                  color: props.locked ? lgColors.textMuted : lgColors.danger,
                  cursor: props.locked ? "not-allowed" : "pointer",
                }}
              >
                {Ic.x(12)} Clear workspace source
              </button>
            )}
          </div>
        </div>
      ) : (
        <div style={lgStyles.helper}>
          Complete the Source Snapshot step above to configure snapshot behavior.
        </div>
      )}
    </div>
  );
}
