import { FIELD_META } from "../../../../application/state/fieldMeta";
import { C, F, S_SECTION_LABEL } from "../../../theme/theme";

interface FieldTipsPickerProps {
  tipFields: string[];
  activeField: string | null;
  onFocusField: (field: string) => void;
}

export function FieldTipsPicker({ tipFields, activeField, onFocusField }: FieldTipsPickerProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          ...S_SECTION_LABEL,
          letterSpacing: 1.1,
        }}
      >
        Tips
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
        }}
      >
        {tipFields.map((fieldKey) => {
          const isActive = activeField === fieldKey;
          return (
            <button
              type="button"
              key={fieldKey}
              onClick={() => onFocusField(fieldKey)}
              style={{
                ...{
                  fontSize: 11,
                  fontFamily: F.sans,
                  fontWeight: 700,
                  letterSpacing: 0.2,
                  borderRadius: 99,
                  padding: "3px 9px",
                  cursor: "pointer",
                },
                color: isActive ? C.accent : C.textMid,
                background: isActive ? C.accentBg : C.surfaceAlt,
                border: `1px solid ${isActive ? C.accentBorder : C.border}`,
              }}
            >
              {FIELD_META[fieldKey]?.label || fieldKey}
            </button>
          );
        })}
      </div>
    </div>
  );
}
