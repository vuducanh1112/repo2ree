import { FIELD_META } from "../../../../application/state/fieldMeta";
import { Ic } from "../../../shared/components/Icon";
import { C, F, S_SECTION_LABEL } from "../../../theme/theme";

interface FieldTipsEmptyStateProps {
  assemblyTipFields: string[];
  onFocusField?: (field: string) => void;
  emptyText: string;
}

export function FieldTipsEmptyState({
  assemblyTipFields,
  onFocusField,
  emptyText,
}: FieldTipsEmptyStateProps) {
  if (assemblyTipFields.length > 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          padding: "12px 13px",
          background: C.accentBg,
          border: `1px solid ${C.accentBorder}`,
          borderRadius: 9,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          <span
            style={{
              color: C.accent,
              display: "flex",
            }}
          >
            {Ic.info(13)}
          </span>
          <span
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 0.8,
              color: C.accent,
            }}
          >
            Process tips
          </span>
        </div>
        <p
          style={{
            fontSize: 12,
            color: C.textMid,
            lineHeight: 1.55,
            margin: 0,
          }}
        >
          No field selected. Here are the key tips for this page and process step:
        </p>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {assemblyTipFields.map((fieldKey) => {
            const meta = FIELD_META[fieldKey];
            return (
              <button
                type="button"
                key={fieldKey}
                onClick={() => onFocusField?.(fieldKey)}
                style={{
                  ...{
                    textAlign: "left",
                    padding: "8px 10px",
                    borderRadius: 8,
                    border: `1px solid ${C.accentBorder}`,
                    background: C.surface,
                    display: "flex",
                    flexDirection: "column",
                    gap: 3,
                  },
                  cursor: onFocusField ? "pointer" : "default",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: C.text,
                    fontFamily: F.sans,
                  }}
                >
                  {meta?.label || fieldKey}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    color: C.textMuted,
                    lineHeight: 1.45,
                  }}
                >
                  {meta?.desc || ""}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
        padding: "12px 13px",
        background: C.accentBg,
        border: `1px solid ${C.accentBorder}`,
        borderRadius: 9,
      }}
    >
      <span
        style={{
          color: C.accent,
          flexShrink: 0,
          marginTop: 1,
        }}
      >
        {Ic.info(13)}
      </span>
      <p
        style={{
          fontSize: 13,
          color: C.textMid,
          lineHeight: 1.6,
          margin: 0,
        }}
      >
        {emptyText}
      </p>
    </div>
  );
}
