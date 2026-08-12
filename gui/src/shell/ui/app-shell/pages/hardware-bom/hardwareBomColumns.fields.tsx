import { Input, Select } from "@shell/ui/shared/components/FormControl";
import type { HardwareColumn } from "./hardwareBomColumns.types";

interface CellRenderContext {
  locked: boolean;
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
          <Select
            density="compact"
            disabled={ctx.locked}
            value={value as string}
            onChange={(event) =>
              patch(index, { [spec.field]: event.target.value } as Partial<RowT>)
            }
          >
            {spec.options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        );
      }

      const isNumber = spec.kind === "number";
      return (
        <Input
          density="compact"
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
        />
      );
    },
  }));
}
