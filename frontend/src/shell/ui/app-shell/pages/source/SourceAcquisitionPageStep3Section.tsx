import { Ic } from "../../../shared/components/Icon";
import { Toggle } from "../../../shared/components/Toggle";
import { C, F } from "../../../theme/theme";
import { FieldSection } from "../../components/fieldTips";
import { sourceClearButtonTone, sourceIncludedLabelStyle } from "../../components/statusUiStyles";
import type { AppShellPage } from "../../state/pages";
import { PAGE } from "../../state/pages";
import type { SourceAcquisitionPageProps } from "../sharedAssemblyUi";
import { actionBtn } from "./SourceAcquisitionPageStyles";

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
    <FieldSection
      title="Step 3: Workspace Actions"
      filledCount={props.sourceInWorkspace ? 1 : 0}
      totalCount={1}
    >
      {props.step3Ready ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "10px 0" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={sourceIncludedLabelStyle(props.sourceIncludedEffective)}>
                Include snapshot in REE
              </span>
              <Toggle
                on={props.sourceIncludedEffective}
                disabled={props.sourceIncludedLocked}
                color="#f59e0b"
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
                <span style={{ fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
                  Uploaded source is always included so the archive remains reproducible.
                </span>
              )}
            </div>
          </div>
          <div style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans }}>
            {props.acquisitionNarrative}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => {
                props.focus("sourceAvailable");
                props.onGoAssemblyPage(PAGE.FILES);
              }}
              style={{
                ...actionBtn({
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                }),
                border: `1.5px solid ${C.border}`,
                background: C.surface,
                color: C.textMid,
              }}
              title="Browse files"
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
                  ...actionBtn({
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 7,
                    padding: "8px 12px",
                    fontWeight: 800,
                  }),
                  ...sourceClearButtonTone(props.locked),
                }}
              >
                {Ic.x(12)} Clear workspace source
              </button>
            )}
          </div>
        </div>
      ) : (
        <div style={{ padding: "10px 0", fontSize: 12, color: C.textMuted, fontFamily: F.sans }}>
          Complete Step 2 to unlock this step.
        </div>
      )}
    </FieldSection>
  );
}
