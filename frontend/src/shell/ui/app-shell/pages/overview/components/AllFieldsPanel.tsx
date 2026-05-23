import { useState } from "react";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { Ic } from "../../../../shared/components/Icon";
import { lgBackgrounds, lgColors, lgStyles } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";
import { FIELD_META } from "../../../fieldTips/fieldMeta";

interface AllFieldsPanelProps {
  ree: ReeEditorViewModel;
}

function isEmptyValue(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    value === "" ||
    (typeof value === "object" && Object.keys(value as object).length === 0)
  );
}

export function AllFieldsPanel({ ree }: AllFieldsPanelProps) {
  const [open, setOpen] = useState(false);
  const fields = Object.entries(ree).filter(([key]) => !key.startsWith("_"));
  const setCount = fields.filter(([, value]) => !isEmptyValue(value)).length;

  return (
    <div style={{ ...lgStyles.overviewPanel, marginTop: 20 }}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        style={{
          ...lgStyles.overviewPanelHeaderRow,
          width: "100%",
          border: "none",
          borderBottom: open ? "1px solid rgba(148, 163, 184, 0.24)" : "none",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span style={{ display: "flex", color: lgColors.textMid }}>
          {open ? Ic.chevD(13) : Ic.chevR(13)}
        </span>
        <span style={lgStyles.overviewPanelLabel}>All Fields</span>
        <span
          style={{
            marginLeft: "auto",
            fontSize: 10,
            fontFamily: F.mono,
            color: lgColors.textMuted,
          }}
        >
          {setCount}/{fields.length} set
        </span>
      </button>

      {open && (
        <div style={{ padding: "8px 20px 16px", display: "flex", flexDirection: "column" }}>
          {fields.map(([key, value], index) => {
            const label = FIELD_META[key]?.label || key;
            const isEmpty = isEmptyValue(value);
            const isObject = typeof value === "object" && value !== null && !isEmpty;
            const displayValue: string = isEmpty
              ? "not set"
              : isObject
                ? JSON.stringify(value, null, 2)
                : String(value);
            const isLastRow = index === fields.length - 1;

            return (
              <div
                key={key}
                style={{
                  display: "flex",
                  padding: "10px 0",
                  borderBottom: isLastRow ? "none" : "1px solid rgba(148, 163, 184, 0.24)",
                  alignItems: "flex-start",
                  gap: 16,
                }}
              >
                <div
                  style={{ width: 180, display: "flex", flexDirection: "column", flexShrink: 0 }}
                >
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: F.sans,
                      color: lgColors.textMid,
                      fontWeight: 600,
                    }}
                  >
                    {label}
                  </span>
                  <span style={{ fontFamily: F.mono, fontSize: 9, color: lgColors.textMuted }}>
                    {key}
                  </span>
                </div>
                {isObject ? (
                  <pre
                    style={{
                      margin: 0,
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: lgColors.textMid,
                      whiteSpace: "pre-wrap",
                      background: lgBackgrounds.row,
                      padding: "8px 12px",
                      borderRadius: 6,
                      flex: 1,
                      border: "1px solid rgba(148, 163, 184, 0.3)",
                    }}
                  >
                    {displayValue}
                  </pre>
                ) : (
                  <span
                    style={{
                      fontSize: 12,
                      fontFamily: F.mono,
                      color: isEmpty ? lgColors.textMuted : lgColors.text,
                      fontStyle: isEmpty ? "italic" : "normal",
                      wordBreak: "break-all",
                      flex: 1,
                      marginTop: 1,
                    }}
                  >
                    {displayValue}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
