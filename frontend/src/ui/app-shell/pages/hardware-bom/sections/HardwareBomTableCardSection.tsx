import { Ic } from "../../../../shared/components/Icon";
import { C, F, hoverBg, hoverBorderColor, hoverColor } from "../../../../theme/theme";
import type { HardwareColumn } from "../hardwareBomColumns";
import { actionBtn } from "../hardwareBomPageHelpers";

export function HardwareCardSection<RowT extends { id: string }>({
  title,
  rows,
  columns,
  locked,
  onRemove,
  onAdd,
  addLabel,
}: {
  title: string;
  rows: RowT[];
  columns: HardwareColumn<RowT>[];
  locked: boolean;
  onRemove: (index: number) => void;
  onAdd: () => void;
  addLabel: string;
}) {
  const gridTemplateColumns = `${columns.map((column) => column.width).join(" ")} auto`;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: C.textMid }}>{title}</div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns,
          gap: 8,
          alignItems: "center",
          padding: "0 12px",
        }}
      >
        {columns.map((column) => (
          <div
            key={column.key}
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: 0.4,
              textTransform: "uppercase",
              color: C.textMuted,
              fontFamily: F.sans,
            }}
          >
            {column.label}
          </div>
        ))}
        <div />
      </div>
      {rows.map((row, index) => (
        <div
          key={row.id}
          style={{
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            background: C.surfaceAlt,
            padding: 12,
            boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns,
              gap: 8,
              alignItems: "center",
            }}
          >
            {columns.map((column) => (
              <div key={column.key}>{column.render(row, index)}</div>
            ))}
            {!locked ? (
              <button
                type="button"
                onClick={() => onRemove(index)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: C.textMuted,
                  padding: "4px",
                  display: "flex",
                  borderRadius: 5,
                }}
                {...hoverColor("#dc2626", C.textMuted)}
                {...hoverBg("#fef2f2", "transparent")}
              >
                {Ic.x()}
              </button>
            ) : (
              <div />
            )}
          </div>
        </div>
      ))}
      {!locked && (
        <button
          type="button"
          onClick={onAdd}
          style={{
            ...actionBtn({
              border: `1.5px dashed ${C.borderMid}`,
              padding: "6px 10px",
              background: "transparent",
              color: C.textMuted,
            }),
            display: "flex",
            alignItems: "center",
            gap: 6,
            cursor: "pointer",
            width: "fit-content",
          }}
          {...hoverBorderColor(C.accent, C.borderMid)}
          {...hoverColor(C.accent, C.textMuted)}
        >
          {Ic.plus()} {addLabel}
        </button>
      )}
    </div>
  );
}
