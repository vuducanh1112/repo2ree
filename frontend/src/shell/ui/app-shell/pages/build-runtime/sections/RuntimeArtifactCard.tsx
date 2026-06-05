import {
  runtimeArtifactStatus,
  runtimeArtifactStatusLabel,
} from "../../../../../../core/ree-assembly/buildRuntimeUiState";
import type { FileTreeNode } from "../../../../../../core/workspace/FileTree";
import { Ic } from "../../../../shared/components/Icon";
import {
  lgColors,
  lgContentCard,
  lgInfoBanner,
  lgStatusBadge,
  lgStyles,
} from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";
import { FilePicker } from "../../../components/scriptAndFile";

interface RuntimeArtifactCardProps {
  runtimePath: string;
  runtimeSize: string | null;
  runtimePathExists: boolean;
  files: FileTreeNode[];
  onRuntimeChange: (path: string) => void;
}

export function RuntimeArtifactCard({
  runtimePath,
  runtimeSize,
  runtimePathExists,
  files,
  onRuntimeChange,
}: RuntimeArtifactCardProps) {
  const hasRuntime = !!runtimePath;
  const status = runtimeArtifactStatus({
    hasRuntime,
    runtimePathExists,
  });
  const ok = status === "ready";

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
              Pick the workspace file that downstream SBOM and activation use.
            </div>
          </div>
        </div>
        <span style={lgStatusBadge(ok)}>{runtimeArtifactStatusLabel(status)}</span>
      </div>

      <FilePicker
        value={runtimePath}
        onChange={onRuntimeChange}
        files={files}
        placeholder="runtime.tar.gz"
      />

      {hasRuntime && (
        <div style={{ ...lgInfoBanner(ok ? "success" : "danger"), marginTop: 12 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: ok ? lgColors.success : lgColors.danger,
              fontFamily: F.sans,
              fontWeight: 700,
              flex: 1,
              minWidth: 0,
            }}
          >
            {ok ? Ic.check(13) : Ic.info(13)}
            <code style={{ overflowWrap: "anywhere" }}>{runtimePath}</code>
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
