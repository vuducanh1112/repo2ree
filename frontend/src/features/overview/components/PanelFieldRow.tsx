import React from "react";
import { C, F } from "../../../constants/theme";

export interface PanelFieldRowProps {
  label: string;
  value: string | null | undefined;
  emptyText?: string;
  filled: boolean;
  dotColor: string;
  dotGlow: string;
  labelColor: string;
  labelBg: string;
  labelBorderColor: string;
  onClick?: () => void;
  isLast?: boolean;
}

export function PanelFieldRow({
  label,
  value,
  emptyText = "not set",
  filled,
  dotColor,
  dotGlow,
  labelColor,
  labelBg,
  labelBorderColor,
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
    <div
      style={{
        position: "relative",
      }}
    >
      <button
        type="button"
        ref={rowRef}
        onClick={onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{
          ...{
            display: "flex",
            alignItems: "stretch",
            width: "100%",
            textAlign: "left",
            border: "none",
            transition: "background 0.12s",
          },
          background: hovered && onClick ? C.surfaceAlt : "transparent",
          borderBottom: isLast ? "none" : `1px solid ${C.border}`,
          cursor: onClick ? "pointer" : "default",
        }}
      >
        <div
          style={{
            ...{
              display: "flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 8px",
              minWidth: 80,
              maxWidth: 80,
              flexShrink: 0,
            },
            borderRight: `1px solid ${filled ? labelBorderColor : C.border}`,
            background: filled ? labelBg : "transparent",
          }}
        >
          <div
            style={{
              ...{
                width: 5,
                height: 5,
                borderRadius: "50%",
                flexShrink: 0,
              },
              background: filled ? dotColor : "#d1d5db",
              boxShadow: filled ? `0 0 5px ${dotGlow}` : "none",
            }}
          />
          <span
            style={{
              ...{
                fontSize: 10,
                fontFamily: F.sans,
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              },
              color: filled ? labelColor : C.textMuted,
            }}
          >
            {label}
          </span>
        </div>
        <div
          style={{
            padding: "4px 8px",
            flex: 1,
            minWidth: 0,
          }}
        >
          <span
            ref={valueRef}
            style={{
              ...{
                fontSize: 10,
                fontFamily: F.mono,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "block",
              },
              color: filled ? C.textMid : C.textMuted,
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
            ...{
              position: "fixed",
              zIndex: 9999,
              background: C.text,
              color: "#fff",
              fontFamily: F.mono,
              fontSize: 11,
              padding: "5px 9px",
              borderRadius: 6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxWidth: 320,
              boxShadow: "0 4px 16px rgba(0,0,0,0.22)",
              pointerEvents: "none",
              lineHeight: 1.5,
            },
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
              background: C.text,
              transform: "rotate(45deg)",
              borderRadius: 1,
            }}
          />
        </div>
      )}
    </div>
  );
}
