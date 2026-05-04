import { FIELD_META } from "../../../../application/app-shell/fieldMeta";
import { C } from "../../../theme/theme";
import { FieldTipCard } from "./FieldTipCard";
import { FieldTipsEmptyState } from "./FieldTipsEmptyState";
import { FieldTipsGeneral } from "./FieldTipsGeneral";
import { FieldTipsPicker } from "./FieldTipsPicker";

interface FieldTipsSidebarProps {
  focusedField: string | null;
  onFocusField?: (field: string) => void;
  onClear: () => void;
  tipFields?: string[];
  emptyMessage?: string;
  generalTips?: string[];
  generalTitle?: string;
}
export function FieldTipsSidebar({
  focusedField,
  onFocusField,
  onClear,
  tipFields,
  emptyMessage,
  generalTips = [],
  generalTitle = "Step Purpose",
}: FieldTipsSidebarProps) {
  const activeField =
    focusedField && (!tipFields || tipFields.includes(focusedField)) ? focusedField : null;
  const showFieldPicker = !!(tipFields && tipFields.length > 0 && onFocusField);
  const emptyText =
    emptyMessage ||
    "Click any field — here or in the status bar above — to see examples, format rules, and commands.";
  const workflowTipFields = (tipFields || []).filter((fieldKey) => !!FIELD_META[fieldKey]);

  return (
    <div
      style={{
        width: 296,
        borderLeft: `1px solid ${C.border}`,
        background: C.surface,
        overflowY: "auto",
        padding: 20,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      {showFieldPicker && tipFields && onFocusField && (
        <FieldTipsPicker
          tipFields={tipFields}
          activeField={activeField}
          onFocusField={onFocusField}
        />
      )}

      {generalTips.length > 0 && (
        <FieldTipsGeneral generalTips={generalTips} generalTitle={generalTitle} />
      )}

      {activeField ? (
        <FieldTipCard fieldKey={activeField} onDismiss={onClear} />
      ) : (
        <FieldTipsEmptyState
          workflowTipFields={workflowTipFields}
          onFocusField={onFocusField}
          emptyText={emptyText}
        />
      )}
    </div>
  );
}
