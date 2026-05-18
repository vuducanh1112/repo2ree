import {
  activationRunLabel,
  canRunActivation,
} from "../../../../../../core/ree-assembly/activationUiState";
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

interface ActivationRunConsoleProps {
  color: string;
  runtimePath: string;
  runtimePathExists: boolean;
  scriptPath: string;
  scriptPresent: boolean;
  running: boolean;
  runDone: boolean;
  missing: ReeAssemblyRequirement[];
  onRun: () => void;
  onCancel?: () => void;
  onGoFields?: () => void;
}

export function ActivationRunConsole({
  color,
  runtimePath,
  runtimePathExists,
  scriptPath,
  scriptPresent,
  running,
  runDone,
  missing,
  onRun,
  onCancel,
  onGoFields,
}: ActivationRunConsoleProps) {
  const scriptFileMissing = !!scriptPath && !scriptPresent;
  const canRun = canRunActivation({
    running,
    hasMissing: missing.length > 0,
    runtimePathExists,
    scriptFileMissing,
  });
  const disabled = !canRun;
  const label = activationRunLabel({ running, runDone });

  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ color, display: "flex" }}>{Ic.play(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Run Activation</h2>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />
        {runtimePath && !runtimePathExists && (
          <div style={lgInfoBanner("danger")}>
            <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
            <span style={{ fontSize: 12, color: lgColors.danger }}>
              Runtime file must exist before the activation test can run.
            </span>
          </div>
        )}
        {scriptFileMissing && (
          <div style={lgInfoBanner("danger")}>
            <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
            <span style={{ fontSize: 12, color: lgColors.danger }}>
              Activation script file must exist before the activation test can run.
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
        {canRun && runtimePath && (
          <span style={lgStyles.helper}>
            Loads <code>{runtimePath}</code> and runs the activation smoke test.
          </span>
        )}
      </div>
    </section>
  );
}
