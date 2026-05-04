import type React from "react";
import { FIELD_META } from "../../../../application/app-shell/fieldMeta";
import { triggerOnEnterOrSpace } from "../../../shared/keyboard";
import {
  C,
  F,
  S_FIELD_ROW_BASE,
  S_FIELD_ROW_CONTENT,
  S_FIELD_ROW_DESC,
  S_FIELD_ROW_HEAD,
  S_FIELD_ROW_LABEL_BASE,
  S_FIELD_ROW_REQUIRED_BADGE,
} from "../../../theme/theme";
import { tipTargetChip } from "./shared";

interface FieldRowProps {
  fieldKey: string;
  required?: boolean;
  children: React.ReactNode;
  locked?: boolean;
  onFocus?: () => void;
  active?: boolean;
}
export function FieldRow({ fieldKey, required, children, locked, onFocus, active }: FieldRowProps) {
  const meta = FIELD_META[fieldKey] || { label: fieldKey, desc: "" };
  const tipEnabled = !!onFocus;
  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: section container intentionally acts as full-surface tip target.
    <div
      id={`field-${fieldKey}`}
      onClick={tipEnabled ? () => onFocus?.() : undefined}
      role={tipEnabled ? "button" : undefined}
      tabIndex={tipEnabled ? 0 : undefined}
      onKeyDown={(event) => {
        if (!tipEnabled) return;
        triggerOnEnterOrSpace(event, () => onFocus?.());
      }}
      style={{
        ...S_FIELD_ROW_BASE,
        background: active ? `${C.accentBg}75` : "transparent",
        cursor: tipEnabled ? "pointer" : "default",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      <div>
        <div style={S_FIELD_ROW_HEAD}>
          <span
            style={{
              ...S_FIELD_ROW_LABEL_BASE,
              color: active ? C.accent : C.text,
            }}
          >
            {meta.label}
          </span>
          {tipEnabled && tipTargetChip(!!active)}
          {required && <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>}
          {locked && fieldKey !== "swhid" && (
            <span
              style={{
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
                background: C.surfaceAlt,
                border: `1px solid ${C.border}`,
                borderRadius: 3,
                padding: "1px 4px",
              }}
            >
              locked
            </span>
          )}
        </div>
        <p style={S_FIELD_ROW_DESC}>{meta.desc}</p>
      </div>
      <div style={S_FIELD_ROW_CONTENT}>{children}</div>
    </div>
  );
}
