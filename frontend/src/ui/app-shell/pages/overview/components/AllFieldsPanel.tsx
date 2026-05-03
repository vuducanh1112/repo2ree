import { FIELD_META } from "../../../../../application/app-shell/fieldMeta";
import type { ReeViewState } from "../../../../../domain/ree/ReeViewState";
import { C, F } from "../../../../theme/theme";

interface AllFieldsPanelProps {
  ree: ReeViewState;
}

export function AllFieldsPanel({ ree }: AllFieldsPanelProps) {
  return (
    <div
      style={{
        marginTop: 32,
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: "16px 20px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.textMuted }} />
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: C.text,
            letterSpacing: 0.3,
            fontFamily: F.sans,
          }}
        >
          All Fields
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        {Object.entries(ree)
          .filter(([key]) => !key.startsWith("_"))
          .map(([key, value], index, fields) => {
            const label = FIELD_META[key]?.label || key;
            const isEmpty =
              value === undefined ||
              value === null ||
              value === "" ||
              (typeof value === "object" && Object.keys(value).length === 0);

            let displayValue: string = isEmpty ? "not set" : String(value);
            if (typeof value === "object" && value !== null && !isEmpty) {
              displayValue = JSON.stringify(value, null, 2);
            }

            const isLastRow = index === fields.length - 1;

            return (
              <div
                key={key}
                style={{
                  display: "flex",
                  padding: "10px 0",
                  borderBottom: isLastRow ? "none" : `1px solid ${C.border}`,
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
                      color: C.textMid,
                      fontWeight: 600,
                    }}
                  >
                    {label}
                  </span>
                  <span style={{ fontFamily: F.mono, fontSize: 9, color: C.textMuted }}>{key}</span>
                </div>
                {typeof value === "object" && value !== null && !isEmpty ? (
                  <pre
                    style={{
                      margin: 0,
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: C.textMid,
                      whiteSpace: "pre-wrap",
                      background: C.surfaceAlt,
                      padding: "8px 12px",
                      borderRadius: 6,
                      flex: 1,
                      border: `1px solid ${C.border}`,
                    }}
                  >
                    {String(displayValue)}
                  </pre>
                ) : (
                  <span
                    style={{
                      fontSize: 12,
                      fontFamily: F.mono,
                      color: isEmpty ? C.textMuted : C.text,
                      fontStyle: isEmpty ? "italic" : "normal",
                      wordBreak: "break-all",
                      flex: 1,
                      marginTop: 1,
                    }}
                  >
                    {String(displayValue)}
                  </span>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}
