import type React from "react";
import {
  type CPURow,
  type GPURow,
  type HardwareBomDraft,
  type MemoryRow,
  type NetworkRow,
  newCpuRow,
  newGpuRow,
  newMemoryRow,
  newNetworkRow,
  newStorageRow,
  type StorageRow,
} from "../../../../../domain/hbom/hardwareBomDraft";
import { Ic } from "../../../../shared/components/Icon";
import { C, F, hoverBg, hoverBorderColor, hoverColor } from "../../../../theme/theme";
import { FieldRow, FieldSection } from "../../../components/fieldTips";
import {
  createCpuColumns,
  createGpuColumns,
  createMemoryColumns,
  createNetworkColumns,
  createStorageColumns,
  type HardwareColumn,
} from "../hardwareBomColumns";
import { actionBtn, inp, selectInp } from "../hardwareBomPageHelpers";

interface HardwareSectionConfig<RowT extends { id: string }> {
  fieldTitle: string;
  sectionTitle: string;
  icon: React.ReactNode;
  subtitle: string;
  rows: RowT[];
  columns: HardwareColumn<RowT>[];
  addLabel: string;
  onAdd: () => void;
  onRemove: (index: number) => void;
}

type HardwareCategoryKey = keyof HardwareBomDraft;

interface HardwareBomTablesSectionProps {
  draft: HardwareBomDraft;
  locked: boolean;
  focusedField: string | null;
  onFocusField: (key: string) => void;
  onDraftChange: (draft: HardwareBomDraft) => void;
}

function HardwareCardSection<RowT extends { id: string }>({
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

export function HardwareBomTablesSection({
  draft,
  locked,
  focusedField,
  onFocusField,
  onDraftChange,
}: HardwareBomTablesSectionProps) {
  const setRows = <K extends HardwareCategoryKey>(key: K, rows: HardwareBomDraft[K]) => {
    onDraftChange({ ...draft, [key]: rows } as HardwareBomDraft);
  };

  const patchCpuRow = (index: number, patch: Partial<CPURow>) =>
    setRows(
      "cpus",
      draft.cpus.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );

  const patchGpuRow = (index: number, patch: Partial<GPURow>) =>
    setRows(
      "gpus",
      draft.gpus.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );

  const patchMemoryRow = (index: number, patch: Partial<MemoryRow>) =>
    setRows(
      "memory",
      draft.memory.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );

  const patchStorageRow = (index: number, patch: Partial<StorageRow>) =>
    setRows(
      "storage",
      draft.storage.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );

  const patchNetworkRow = (index: number, patch: Partial<NetworkRow>) =>
    setRows(
      "network",
      draft.network.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );

  const removeRowAtIndex = (key: HardwareCategoryKey, index: number) => {
    setRows(
      key,
      draft[key].filter((_, itemIndex) => itemIndex !== index) as HardwareBomDraft[typeof key],
    );
  };

  const renderHardwareSection = <RowT extends { id: string }>({
    fieldTitle,
    sectionTitle,
    icon,
    subtitle,
    rows,
    columns,
    addLabel,
    onAdd,
    onRemove,
  }: HardwareSectionConfig<RowT>) => (
    <FieldSection
      title={fieldTitle}
      icon={icon}
      subtitle={subtitle}
      filledCount={rows.length}
      totalCount={rows.length}
    >
      <FieldRow
        fieldKey="hardware_description"
        locked={locked}
        onFocus={() => onFocusField("hardware_description")}
        active={focusedField === "hardware_description"}
      >
        <div style={{ padding: "12px 0" }}>
          <HardwareCardSection
            title={sectionTitle}
            rows={rows}
            columns={columns}
            locked={locked}
            onRemove={onRemove}
            onAdd={onAdd}
            addLabel={addLabel}
          />
        </div>
      </FieldRow>
    </FieldSection>
  );

  const cpuColumns = createCpuColumns({
    locked,
    inp,
    selectInp,
    onFocusHardwareDescription: () => onFocusField("hardware_description"),
    patchCpuRow,
  });
  const gpuColumns = createGpuColumns({
    locked,
    inp,
    selectInp,
    patchGpuRow,
  });
  const memoryColumns = createMemoryColumns({
    locked,
    inp,
    selectInp,
    patchMemoryRow,
  });
  const storageColumns = createStorageColumns({
    locked,
    inp,
    selectInp,
    patchStorageRow,
  });
  const networkColumns = createNetworkColumns({
    locked,
    inp,
    selectInp,
    patchNetworkRow,
  });

  return (
    <>
      {renderHardwareSection({
        fieldTitle: "CPU",
        sectionTitle: "CPUs",
        icon: Ic.chip(),
        subtitle: "processor packages and topology",
        rows: draft.cpus,
        columns: cpuColumns,
        addLabel: "Add CPU",
        onRemove: (index) => removeRowAtIndex("cpus", index),
        onAdd: () => setRows("cpus", [...draft.cpus, newCpuRow()]),
      })}

      {renderHardwareSection({
        fieldTitle: "GPU",
        sectionTitle: "GPUs",
        icon: Ic.chip(),
        subtitle: "accelerators and graphics devices",
        rows: draft.gpus,
        columns: gpuColumns,
        addLabel: "Add GPU",
        onRemove: (index) => removeRowAtIndex("gpus", index),
        onAdd: () => setRows("gpus", [...draft.gpus, newGpuRow()]),
      })}

      {renderHardwareSection({
        fieldTitle: "Memory",
        sectionTitle: "Memory",
        icon: Ic.chip(),
        subtitle: "modules and aggregate RAM assumptions",
        rows: draft.memory,
        columns: memoryColumns,
        addLabel: "Add memory",
        onRemove: (index) => removeRowAtIndex("memory", index),
        onAdd: () => setRows("memory", [...draft.memory, newMemoryRow()]),
      })}

      {renderHardwareSection({
        fieldTitle: "Storage",
        sectionTitle: "Storage",
        icon: Ic.chip(),
        subtitle: "disks, SSDs, and runtime capacity",
        rows: draft.storage,
        columns: storageColumns,
        addLabel: "Add storage",
        onRemove: (index) => removeRowAtIndex("storage", index),
        onAdd: () => setRows("storage", [...draft.storage, newStorageRow()]),
      })}

      {renderHardwareSection({
        fieldTitle: "Network",
        sectionTitle: "Network",
        icon: Ic.chip(),
        subtitle: "host interfaces and bandwidth",
        rows: draft.network,
        columns: networkColumns,
        addLabel: "Add network",
        onRemove: (index) => removeRowAtIndex("network", index),
        onAdd: () => setRows("network", [...draft.network, newNetworkRow()]),
      })}
    </>
  );
}
