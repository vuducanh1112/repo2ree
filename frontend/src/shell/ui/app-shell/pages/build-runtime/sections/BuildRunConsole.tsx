import type { ReeAssemblyRequirement } from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import {
  lgColors,
  lgInfoBanner,
  lgPrimaryActionButton,
  lgStyles,
} from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

interface BuildRunConsoleProps {
  running: boolean;
  runDone: boolean;
  missing: ReeAssemblyRequirement[];
  onRun: () => void;
  onCancel?: () => void;
  onGoFields?: () => void;
}

export function BuildRunConsole({
  running,
  runDone,
  missing,
  onRun,
  onCancel,
  onGoFields,
}: BuildRunConsoleProps) {
  const hasMissing = missing.length > 0;
  const disabled = running || hasMissing;
  const buttonLabel = running ? "Building…" : runDone ? "Re-build" : "Run build";

  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.play(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Run Build</h2>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {hasMissing && (
          <div
            style={{ ...lgInfoBanner("danger"), flexDirection: "column", alignItems: "stretch" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: lgColors.danger }}>
                Required inputs missing
              </span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {missing.map((item) => (
                <span
                  key={item.field}
                  style={{
                    fontSize: 11,
                    fontFamily: F.sans,
                    color: lgColors.danger,
                    background: "rgba(255,255,255,0.55)",
                    border: `1px solid ${lgColors.dangerBorder}`,
                    borderRadius: 4,
                    padding: "2px 8px",
                  }}
                >
                  {item.label}
                </span>
              ))}
            </div>
            {onGoFields && (
              <button
                type="button"
                onClick={onGoFields}
                style={{
                  alignSelf: "flex-start",
                  fontSize: 11,
                  fontWeight: 700,
                  border: `1px solid ${lgColors.dangerBorder}`,
                  background: "rgba(255,255,255,0.6)",
                  color: lgColors.danger,
                  borderRadius: 6,
                  padding: "4px 10px",
                  cursor: "pointer",
                }}
              >
                Jump to required field
              </button>
            )}
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
          {buttonLabel}
        </button>
        {running && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              border: `1px solid ${lgColors.dangerBorder}`,
              background: "rgba(255, 241, 242, 0.82)",
              color: lgColors.danger,
              padding: "8px 14px",
              borderRadius: 8,
              fontWeight: 700,
              cursor: "pointer",
              width: "100%",
            }}
          >
            {Ic.x(14)} Cancel
          </button>
        )}
        {!hasMissing && (
          <span style={lgStyles.helper}>Executes the build script and records logs.</span>
        )}
      </div>
    </section>
  );
}
