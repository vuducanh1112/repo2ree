import type React from "react";
import type { HardwareColumn } from "./hardwareBomColumns.types";

type CellStyle = (locked: boolean, extra?: React.CSSProperties) => React.CSSProperties;

interface CellRenderContext {
  locked: boolean;
  inp: CellStyle;
  selectInp: CellStyle;
  /** Invoked on focus of fields declared with `focusOnEdit`. */
  onFocus?: () => void;
}

/**
 * Declarative description of one hardware-table column. `key` is the column id
 * (layout/React); `field` is the row property the cell reads and patches.
 */
export type FieldSpec<RowT> = {
  key: string;
  label: string;
  width: string;
  field: keyof RowT;
} & (
  | { kind: "text"; placeholder: string; focusOnEdit?: boolean }
  | { kind: "number"; placeholder: string; min: number }
  | { kind: "select"; options: readonly string[] }
);

/** Turns declarative field specs into the `HardwareColumn` renderers the table consumes. */
export function buildColumns<RowT>(
  specs: FieldSpec<RowT>[],
  patch: (index: number, patch: Partial<RowT>) => void,
  ctx: CellRenderContext,
): HardwareColumn<RowT>[] {
  return specs.map((spec) => ({
    key: spec.key,
    label: spec.label,
    width: spec.width,
    render: (row, index) => {
      const value = row[spec.field] as string | number;

      if (spec.kind === "select") {
        return (
          <select
            disabled={ctx.locked}
            value={value as string}
            onChange={(event) =>
              patch(index, { [spec.field]: event.target.value } as Partial<RowT>)
            }
            style={ctx.selectInp(ctx.locked)}
          >
            {spec.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        );
      }

      const isNumber = spec.kind === "number";
      return (
        <input
          disabled={ctx.locked}
          type={isNumber ? "number" : undefined}
          min={isNumber ? spec.min : undefined}
          value={value}
          placeholder={spec.placeholder}
          onFocus={spec.kind === "text" && spec.focusOnEdit ? ctx.onFocus : undefined}
          onChange={(event) =>
            patch(index, {
              [spec.field]: isNumber ? Number(event.target.value) : event.target.value,
            } as Partial<RowT>)
          }
          style={ctx.inp(ctx.locked)}
        />
      );
    },
  }));
}
