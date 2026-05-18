import type { ReeAssemblyRequirement } from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import {
  lgColors,
  lgInfoBanner,
  lgPrimaryActionButton,
  lgStyles,
} from "../../../../theme/lightGlassTheme";
import { GlassCancelButton } from "../../../components/GlassCancelButton";
import { MissingInputsBanner } from "../../runtime-environment/MissingInputsBanner";

interface SbomRunConsoleProps {
  color: string;
  runtimePath: string;
  runtimePathExists: boolean;
  running: boolean;
  runDone: boolean;
  missing: ReeAssemblyRequirement[];
  onRun: () => void;
  onCancel?: () => void;
  onGoFields?: () => void;
}

export function SbomRunConsole({
  color,
  runtimePath,
  runtimePathExists,
  running,
  runDone,
  missing,
  onRun,
  onCancel,
  onGoFields,
}: SbomRunConsoleProps) {
  const hasMissing = missing.length > 0;
  const disabled = running || hasMissing || !runtimePathExists;
  const label = running ? "Generating..." : runDone ? "Regenerate SBOM" : "Generate SBOM";
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ color, display: "flex" }}>{Ic.play(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Run SBOM</h2>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />
        {runtimePath && !runtimePathExists && (
          <div style={lgInfoBanner("danger")}>
            <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
            <span style={{ fontSize: 12, color: lgColors.danger }}>
              Runtime file must exist before SBOM generation can run.
            </span>
          </div>
        )}
        {!runtimePath && !hasMissing && (
          <div style={lgInfoBanner("muted")}>
            <span style={{ color: lgColors.textMuted, display: "flex" }}>{Ic.info(13)}</span>
            <span style={{ fontSize: 12, color: lgColors.textMid }}>
              Select a runtime artifact on the build tab first.
            </span>
          </div>
        )}
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          style={{ ...lgPrimaryActionButton(disabled), width: "100%" }}
        >
          <span
            style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
          >
            {running ? Ic.loader(14) : Ic.play(14)}
          </span>
          {label}
        </button>
        {running && onCancel && <GlassCancelButton onClick={onCancel} />}
        {!disabled && (
          <span style={lgStyles.helper}>
            Scans <code>{runtimePath}</code> and writes <code>sbom.json</code>.
          </span>
        )}
      </div>
    </section>
  );
}
