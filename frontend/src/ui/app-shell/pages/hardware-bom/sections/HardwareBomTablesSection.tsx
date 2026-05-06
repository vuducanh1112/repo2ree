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
} from "../../../../../core/hbom/hardwareBomDraft";

function generateRowId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random()}`;
}

import { Ic } from "../../../../shared/components/Icon";
import { FieldRow, FieldSection } from "../../../components/fieldTips";
import {
  createCpuColumns,
  createGpuColumns,
  createMemoryColumns,
  createNetworkColumns,
  createStorageColumns,
  type HardwareColumn,
} from "../hardwareBomColumns";
import { inp, selectInp } from "../hardwareBomPageHelpers";
import { HardwareCardSection } from "./HardwareBomTableCardSection";

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
        onAdd: () => setRows("cpus", [...draft.cpus, newCpuRow(generateRowId)]),
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
        onAdd: () => setRows("gpus", [...draft.gpus, newGpuRow(generateRowId)]),
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
        onAdd: () => setRows("memory", [...draft.memory, newMemoryRow(generateRowId)]),
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
        onAdd: () => setRows("storage", [...draft.storage, newStorageRow(generateRowId)]),
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
        onAdd: () => setRows("network", [...draft.network, newNetworkRow(generateRowId)]),
      })}
    </>
  );
}
