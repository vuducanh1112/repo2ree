import type React from "react";
import { Ic, Svg } from "../../../shared/components/Icon";
import { C, F, hoverBg, hoverColor, hoverIf } from "../../../theme/theme";

export function FilePickerInputRow(props: {
  draft: string;
  disabled?: boolean;
  placeholder?: string;
  onFocus?: () => void;
  open: boolean;
  previewOpen: boolean;
  isValid: boolean | null;
  notFound: boolean;
  wrongFormat: boolean;
  typeStyle: { label: string; bg: string; color: string; border: string };
  borderColor: string;
  onDraftChange: (value: string) => void;
  onToggleOpen: () => void;
  onTogglePreview: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        overflow: "hidden",
        transition: "border-color 0.2s",
        border: `1.5px solid ${props.borderColor}`,
        borderRadius: props.isValid && props.previewOpen ? "7px 7px 0 0" : "7px",
        background: props.disabled ? C.surfaceAlt : C.surface,
        boxShadow: props.isValid
          ? "0 0 0 3px #22c55e10"
          : props.notFound || props.wrongFormat
            ? "0 0 0 3px #f9731610"
            : "none",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 8px 0 10px",
          flexShrink: 0,
          transition: "color 0.2s",
          color:
            props.notFound || props.wrongFormat
              ? "#f97316"
              : props.isValid
                ? "#22c55e"
                : C.textMuted,
        }}
      >
        {props.notFound || props.wrongFormat ? (
          <Svg
            size={14}
            d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
          />
        ) : props.isValid ? (
          Ic.check(14)
        ) : (
          Ic.file(14)
        )}
      </div>

      <input
        value={props.draft}
        onChange={(event) => props.onDraftChange(event.target.value)}
        disabled={props.disabled}
        placeholder={props.placeholder || "path/to/file"}
        onFocus={props.onFocus}
        style={{
          flex: 1,
          border: "none",
          padding: "7px 4px 7px 0",
          fontSize: 14,
          fontFamily: F.mono,
          color: C.text,
          background: "transparent",
        }}
      />

      {props.isValid && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "0 8px",
            flexShrink: 0,
            borderLeft: `1px solid ${props.typeStyle.border}`,
            background: props.typeStyle.bg,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              fontFamily: F.mono,
              letterSpacing: 0.5,
              textTransform: "uppercase",
              color: props.typeStyle.color,
            }}
          >
            {props.typeStyle.label}
          </span>
        </div>
      )}

      {props.isValid && !props.disabled && (
        <button
          type="button"
          onClick={props.onTogglePreview}
          title={props.previewOpen ? "Hide preview" : "Peek at file contents"}
          style={{
            border: "none",
            padding: "7px 9px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 11,
            fontFamily: F.sans,
            fontWeight: 600,
            transition: "background 0.15s, color 0.15s",
            flexShrink: 0,
            background: props.previewOpen ? "#f0fdf4" : C.surfaceAlt,
            borderLeft: `1px solid ${props.previewOpen ? "#bbf7d0" : C.border}`,
            color: props.previewOpen ? "#16a34a" : C.textMid,
          }}
          {...hoverIf(!props.previewOpen, hoverBg(C.accentBg, C.surfaceAlt))}
          {...hoverIf(!props.previewOpen, hoverColor(C.accent, C.textMid))}
        >
          {Ic.terminal(13)}
          <span style={{ display: "none" }}>{props.previewOpen ? "hide" : "peek"}</span>
        </button>
      )}

      {!props.disabled && (
        <button
          type="button"
          onClick={props.onToggleOpen}
          title="Browse repository files"
          style={{
            border: "none",
            padding: "7px 9px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            transition: "background 0.15s, color 0.15s",
            background: props.open ? C.accentBg : C.surfaceAlt,
            borderLeft: `1px solid ${C.border}`,
            color: props.open ? C.accent : C.textMid,
          }}
          {...hoverIf(!props.open, hoverBg(C.accentBg, C.surfaceAlt))}
          {...hoverIf(!props.open, hoverColor(C.accent, C.textMid))}
        >
          {Ic.folder()}
        </button>
      )}
    </div>
  );
}

export function FilePickerDropdown(props: {
  open: boolean;
  paths: string[];
  filterFn?: (path: string) => boolean;
  draft: string;
  onSelect: (path: string) => void;
  style?: React.CSSProperties;
}) {
  if (!props.open) return null;
  return (
    <div
      style={{
        ...(props.style ?? { position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0 }),
        zIndex: 9999,
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
        maxHeight: 240,
        overflowY: "auto",
      }}
    >
      {props.paths.length === 0 ? (
        <div
          style={{
            padding: "12px",
            fontSize: 13,
            color: C.textMuted,
            fontFamily: F.sans,
            textAlign: "center",
          }}
        >
          {props.filterFn ? "No matching files in repository" : "No files in repository"}
        </div>
      ) : (
        props.paths.map((path) => (
          <button
            type="button"
            key={path}
            onClick={() => props.onSelect(path)}
            style={{
              padding: "7px 12px",
              fontSize: 13,
              fontFamily: F.mono,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              border: "none",
              textAlign: "left",
              width: "100%",
              background: props.draft === path ? C.accentBg : "transparent",
              color: props.draft === path ? C.accent : C.textMid,
            }}
            {...hoverIf(props.draft !== path, hoverBg(C.surfaceAlt, "transparent"))}
          >
            <span style={{ display: "flex", opacity: 0.5 }}>{Ic.file(12)}</span>
            {path}
          </button>
        ))
      )}
    </div>
  );
}
