import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgTree } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";

export function FilesEmptyState() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: lgColors.textMuted,
        flexDirection: "column",
        gap: 8,
        background: lgTree.viewerBg,
      }}
    >
      <span style={{ display: "flex", opacity: 0.3 }}>{Ic.file(28)}</span>
      <span style={{ fontSize: 13, fontFamily: F.sans }}>Select a file to view</span>
    </div>
  );
}
