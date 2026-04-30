import { Ic } from "../../shared/components/Icon";
import { C, F, hoverBg, hoverColor } from "../../theme/theme";

interface ReviewerHeaderProps {
  title: string;
  onBack: () => void;
}

export function ReviewerHeader({ title, onBack }: ReviewerHeaderProps) {
  return (
    <header
      style={{
        height: 48,
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "0 16px",
        position: "sticky",
        top: 0,
        zIndex: 100,
        flexShrink: 0,
        boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
      }}
    >
      <button
        type="button"
        onClick={onBack}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 5,
          color: C.textMuted,
          padding: "4px 8px",
          borderRadius: 6,
          transition: "all 0.12s",
        }}
        {...hoverColor(C.textMid, C.textMuted)}
        {...hoverBg(C.surfaceAlt, "transparent")}
      >
        {Ic.arrowLeft()}
        <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
      </button>
      <div style={{ width: 1, height: 18, background: C.border }} />
      <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
      <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
        REE Reviewer
      </span>
      <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
      <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>{title}</span>
      <div style={{ flex: 1 }} />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 10px",
          background: "#fef3c7",
          border: "1px solid #fde68a",
          borderRadius: 6,
        }}
      >
        <span style={{ color: "#b45309", display: "flex" }}>{Ic.star(12)}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "#92400e",
            fontFamily: F.sans,
            letterSpacing: 0.3,
          }}
        >
          REVIEWER MODE
        </span>
      </div>
    </header>
  );
}
