import { Ic } from "../../../../shared/components/Icon";
import {
  S_FIELD_HELP_TEXT_SMALL,
  S_FIELD_LABEL_TEXT_SM,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FLEX_ROW_CENTER_GAP_6,
  S_SECTION_LABEL,
} from "../../../../theme/theme";
import { FieldRow, FieldSection } from "../../../components/fieldTips";
import { FilePicker, ScriptPanel } from "../../../components/scriptAndFile";
import { SVC_SCRIPT_FIELDS } from "../../sharedAssemblyConstants";
import type { AssemblyPageProps } from "../../sharedAssemblyUi";

interface BuildScriptSectionProps {
  assemblyStep: AssemblyPageProps["assemblyStep"];
  ree: AssemblyPageProps["ree"];
  files: AssemblyPageProps["workspaceFiles"];
  focusedField: string | null;
  setFocusedField: (field: string | null) => void;
  onReeSpecChange: AssemblyPageProps["onReeSpecChange"];
  onPersistWorkspaceFile: AssemblyPageProps["onPersistWorkspaceFile"];
}

export function BuildScriptSection({
  assemblyStep,
  ree,
  files,
  focusedField,
  setFocusedField,
  onReeSpecChange,
  onPersistWorkspaceFile,
}: BuildScriptSectionProps) {
  return (
    <FieldSection
      title="Step 1: Build Script"
      icon={Ic.cpu()}
      filledCount={ree.build_runtime_script ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="build_runtime_script"
        onFocus={() => setFocusedField("build_runtime_script")}
        active={focusedField === "build_runtime_script"}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <div style={S_FLEX_ROW_CENTER_GAP_6}>
            <span style={S_FIELD_LABEL_TEXT_SM}>Shell script</span>
            <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
          </div>
          <div style={S_FIELD_HELP_TEXT_SMALL}>
            Script that builds your runtime environment. The script is responsible for exporting the
            runtime to the file specified in "Expected output" below.
          </div>
          <FilePicker
            disabled={false}
            value={ree.build_runtime_script}
            onChange={(v) =>
              onReeSpecChange?.((current) => ({ ...current, build_runtime_script: v }))
            }
            files={files || []}
            placeholder="build_runtime.sh"
            filterFn={(p) => /\.sh$/i.test(p)}
          />
        </div>

        {!ree.build_runtime_script && (
          <div
            style={{
              marginTop: 12,
              padding: "9px 12px",
              borderRadius: 7,
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              fontSize: 11,
              lineHeight: 1.4,
            }}
          >
            No build script yet? Use a predefined default script in the editor below (Docker, Nix,
            Conda, Python venv).
          </div>
        )}

        <div style={{ marginTop: 14 }}>
          <div style={{ ...S_SECTION_LABEL, marginBottom: 10 }}>Build Script Editor</div>
          {SVC_SCRIPT_FIELDS[assemblyStep.key]?.map((sf) => (
            <ScriptPanel
              key={sf.fieldKey}
              scriptKind={sf.scriptKind || null}
              fieldKey={sf.fieldKey}
              files={files || []}
              onPersistWorkspaceFile={onPersistWorkspaceFile}
              ree={ree}
              onReeSpecChange={onReeSpecChange}
              saveToWorkspaceOnly
            />
          ))}
        </div>
      </FieldRow>
    </FieldSection>
  );
}
