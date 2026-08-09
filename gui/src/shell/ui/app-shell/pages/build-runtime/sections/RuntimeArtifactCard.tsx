import {
  runtimeArtifactStatus,
  runtimeArtifactStatusLabel,
} from "@core/ree-steps/buildRuntimeUiState";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgContentCard,
  lgInfoBanner,
  lgInput,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

interface RuntimeArtifactCardProps {
  runtimePath: string;
  runtimeSize: string | null;
  runtimePathExists: boolean;
  onRuntimeChange: (path: string) => void;
}

/**
 * Declare where the build script writes its runtime. This is authored before
 * the build runs — the build refuses to start without it and fails if nothing
 * lands at the declared path — so it is a free-text declaration, not a picker
 * over files that already exist.
 */
export function RuntimeArtifactCard({
  runtimePath,
  runtimeSize,
  runtimePathExists,
  onRuntimeChange,
}: RuntimeArtifactCardProps) {
  const hasRuntime = !!runtimePath;
  const status = runtimeArtifactStatus({
    hasRuntime,
    runtimePathExists,
  });
  const produced = status === "produced";

  return (
    <div style={lgContentCard()}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: lgColors.blue, display: "flex" }}>{Ic.archive(15)}</span>
          <div>
            <div style={lgStyles.label}>Runtime Artifact</div>
            <div style={lgStyles.helper}>
              Where the build script writes the runtime, relative to the workspace. Downstream SBOM
              and activation read the same path.
            </div>
          </div>
        </div>
        <span style={lgStatusBadge(produced)}>{runtimeArtifactStatusLabel(status)}</span>
      </div>

      <section aria-label="Runtime artifact">
        <input
          type="text"
          aria-label="Runtime output path"
          value={runtimePath}
          placeholder="runtime.tar.gz"
          onChange={(event) => onRuntimeChange(event.target.value)}
          style={{ ...lgInput(false), fontFamily: F.mono }}
        />
      </section>

      {hasRuntime && (
        <div style={{ ...lgInfoBanner(produced ? "success" : "muted"), marginTop: 12 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: produced ? lgColors.success : lgColors.textMid,
              fontFamily: F.sans,
              fontWeight: 700,
              flex: 1,
              minWidth: 0,
            }}
          >
            {produced ? Ic.check(13) : Ic.info(13)}
            <code style={{ overflowWrap: "anywhere" }}>
              {produced ? runtimePath : `${runtimePath} — not built yet`}
            </code>
          </span>
          {runtimeSize && (
            <span
              style={{
                fontSize: 11,
                color: lgColors.textMid,
                fontFamily: F.mono,
                background: "rgba(255,255,255,0.65)",
                border: "1px solid rgba(148, 163, 184, 0.34)",
                borderRadius: 6,
                padding: "2px 8px",
              }}
            >
              {runtimeSize}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
