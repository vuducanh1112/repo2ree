import { Ic } from "../../../shared/components/Icon";
import { C, F } from "../../../theme/theme";

export function FilesEmptyState() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: C.textMuted,
        flexDirection: "column",
        gap: 8,
        background: "#f8fafc",
      }}
    >
      <span style={{ display: "flex", opacity: 0.3 }}>{Ic.file(28)}</span>
      <span style={{ fontSize: 13, fontFamily: F.sans }}>Select a file to view</span>
    </div>
  );
}
