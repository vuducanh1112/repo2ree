import type { CSSProperties } from "react";
import { C, hoverBrightness } from "../../theme/theme";

interface ToggleProps {
  on: boolean;
  disabled?: boolean;
  color: string;
  onChange: () => void;
  title?: string;
  width?: number;
  height?: number;
  knobSize?: number;
  padding?: number;
  offColor?: string;
  style?: CSSProperties;
}

export function Toggle({
  on,
  disabled = false,
  color,
  onChange,
  title,
  width = 32,
  height = 16,
  knobSize = 12,
  padding = 2,
  offColor = C.borderMid,
  style,
}: ToggleProps) {
  return (
    <button
      type="button"
      onClick={onChange}
      aria-pressed={on}
      disabled={disabled}
      title={title}
      style={{
        width,
        height,
        borderRadius: 99,
        border: "none",
        cursor: disabled ? "not-allowed" : "pointer",
        background: on ? color : offColor,
        position: "relative",
        transition: "all 0.18s",
        flexShrink: 0,
        opacity: disabled ? 0.6 : 1,
        ...style,
      }}
      {...(disabled ? {} : hoverBrightness(93))}
    >
      <div
        style={{
          position: "absolute",
          top: padding,
          left: on ? width - knobSize - padding : padding,
          width: knobSize,
          height: knobSize,
          borderRadius: "50%",
          background: "#fff",
          transition: "left 0.18s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
        }}
      />
    </button>
  );
}
