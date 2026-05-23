import React from "react";
import { type LgStageTint, lgColors, lgStageDot } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

interface PanelFieldRowProps {
  label: string;
  value: string | null | undefined;
  emptyText?: string;
  filled: boolean;
  tint: LgStageTint;
  onClick?: () => void;
  isLast?: boolean;
}

export function PanelFieldRow({
  label,
  value,
  emptyText = "not set",
  filled,
  tint,
  onClick,
  isLast,
}: PanelFieldRowProps) {
  const [hovered, setHovered] = React.useState(false);
  const [tooltipPos, setTooltipPos] = React.useState<{ x: number; y: number } | null>(null);
  const [isOverflowing, setIsOverflowing] = React.useState(false);
  const rowRef = React.useRef<HTMLButtonElement>(null);
  const valueRef = React.useRef<HTMLSpanElement>(null);

  const showTooltip = hovered && filled && value && isOverflowing;

  const handleMouseEnter = (mouseEvent: React.MouseEvent<HTMLButtonElement>) => {
    setHovered(true);
    const rect = mouseEvent.currentTarget.getBoundingClientRect();
    setTooltipPos({ x: rect.left, y: rect.top });
    if (valueRef.current) {
      setIsOverflowing(valueRef.current.scrollWidth > valueRef.current.offsetWidth);
    }
  };

  const handleMouseLeave = () => {
    setHovered(false);
    setTooltipPos(null);
  };

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        ref={rowRef}
        onClick={onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          display: "flex",
          alignItems: "stretch",
          width: "100%",
          textAlign: "left",
          border: "none",
          transition: "background 0.12s",
          background: hovered && onClick ? "rgba(239, 246, 255, 0.7)" : "transparent",
          borderBottom: isLast ? "none" : "1px solid rgba(148, 163, 184, 0.24)",
          cursor: onClick ? "pointer" : "default",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 9px",
            minWidth: 84,
            maxWidth: 84,
            flexShrink: 0,
            borderRight: `1px solid ${filled ? tint.border : "rgba(148, 163, 184, 0.24)"}`,
            background: filled ? tint.bg : "transparent",
          }}
        >
          <div style={lgStageDot(tint.line, filled)} />
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              fontWeight: 700,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              color: filled ? tint.ink : lgColors.textMuted,
            }}
          >
            {label}
          </span>
        </div>
        <div style={{ padding: "5px 9px", flex: 1, minWidth: 0 }}>
          <span
            ref={valueRef}
            style={{
              fontSize: 10,
              fontFamily: F.mono,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "block",
              color: filled ? lgColors.textMid : lgColors.textMuted,
              fontStyle: filled ? "normal" : "italic",
            }}
          >
            {filled ? value : emptyText}
          </span>
        </div>
      </button>
      {showTooltip && tooltipPos && (
        <div
          style={{
            position: "fixed",
            zIndex: 9999,
            background: lgColors.text,
            color: "#fff",
            fontFamily: F.mono,
            fontSize: 11,
            padding: "5px 9px",
            borderRadius: 6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            maxWidth: 320,
            boxShadow: "0 4px 16px rgba(15, 23, 42, 0.22)",
            pointerEvents: "none",
            lineHeight: 1.5,
            left: tooltipPos.x,
            top: tooltipPos.y - 34,
          }}
        >
          {value}
          <div
            style={{
              position: "absolute",
              bottom: -5,
              left: 14,
              width: 10,
              height: 10,
              background: lgColors.text,
              transform: "rotate(45deg)",
              borderRadius: 1,
            }}
          />
        </div>
      )}
    </div>
  );
}
