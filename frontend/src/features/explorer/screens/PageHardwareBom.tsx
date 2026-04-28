import React from "react";
import { Ic } from "../../../components/Icon";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverColor,
  S_ACTION_BUTTON_BASE,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_MAIN_COL,
  S_WORKFLOW_PAGE_MAIN_SCROLL,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_ROOT,
} from "../../../constants/theme";
import { useFocusScroll } from "../../../hooks/useFocusScroll";
import type {
  CPUDefinition,
  GPUDefinition,
  HBOM,
  MemoryDefinition,
  NetworkDefinition,
  StorageDefinition,
} from "../../../types";
import { emptyHBOM } from "../../../utils/hbom";
import { FieldRow, FieldSection, FieldTipsSidebar } from "../components/workflow/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../components/workflow/pageChrome";
import { ServiceActionSection, WorkflowLogSection } from "../components/workflow/servicePanels";
import { workflowToneSurfaceStyle } from "../components/workflow/statusUiStyles";
import type { PageHardwareBomProps } from "./sharedWorkflowUi";

type CPURow = CPUDefinition & { id: string; model: string; extra_info: Record<string, unknown> };
type GPURow = GPUDefinition & { id: string; model: string; extra_info: Record<string, unknown> };
type MemoryRow = MemoryDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};
type StorageRow = StorageDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};
type NetworkRow = NetworkDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};

interface HardwareBomDraft {
  cpus: CPURow[];
  gpus: GPURow[];
  memory: MemoryRow[];
  storage: StorageRow[];
  network: NetworkRow[];
}

interface HardwareColumn<RowT> {
  key: string;
  label: string;
  width: string;
  render: (row: RowT, index: number) => React.ReactNode;
}

const MEMORY_TYPES = ["DDR3", "DDR4", "DDR5", "LPDDR4", "LPDDR5", "HBM2", "HBM2e", "HBM3"];
const STORAGE_TYPES = ["HDD", "SSD", "NVMe", "eMMC", "SD"];
const NETWORK_TYPES = ["ethernet", "infiniband", "wifi", "cellular"];

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

const inp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

const selectInp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties =>
  inp(locked, extra);

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

function newCpuRow(): CPURow {
  return {
    id: `cpu-${Date.now()}-${Math.random()}`,
    model: "",
    vendor: "",
    quantity: 1,
    cores_per_cpu: 1,
    threads_per_core: 1,
    architecture: "",
    extra_info: {},
  };
}

function newGpuRow(): GPURow {
  return {
    id: `gpu-${Date.now()}-${Math.random()}`,
    model: "",
    vendor: "",
    quantity: 1,
    memory_gb: 0,
    interface: "",
    extra_info: {},
  };
}

function newMemoryRow(): MemoryRow {
  return {
    id: `memory-${Date.now()}-${Math.random()}`,
    model: "",
    vendor: "",
    quantity: 1,
    capacity_gb: 0,
    memory_type: "DDR5",
    speed_mt_s: 1,
    extra_info: {},
  };
}

function newStorageRow(): StorageRow {
  return {
    id: `storage-${Date.now()}-${Math.random()}`,
    model: "",
    vendor: "",
    quantity: 1,
    capacity_gb: 0,
    storage_type: "NVMe",
    interface: "",
    extra_info: {},
  };
}

function newNetworkRow(): NetworkRow {
  return {
    id: `network-${Date.now()}-${Math.random()}`,
    model: "",
    vendor: "",
    quantity: 1,
    bandwidth_gbps: 0,
    network_type: "ethernet",
    interface: "",
    extra_info: {},
  };
}

function draftFromHBOM(hbom: HBOM, previous?: HardwareBomDraft): HardwareBomDraft {
  return {
    cpus: Object.entries(hbom.cpus).map(([model, item], index) => ({
      id: previous?.cpus[index]?.id || `cpu-${index}`,
      model,
      ...item,
    })),
    gpus: Object.entries(hbom.gpus).map(([model, item], index) => ({
      id: previous?.gpus[index]?.id || `gpu-${index}`,
      model,
      ...item,
    })),
    memory: Object.entries(hbom.memory).map(([model, item], index) => ({
      id: previous?.memory[index]?.id || `memory-${index}`,
      model,
      ...item,
    })),
    storage: Object.entries(hbom.storage).map(([model, item], index) => ({
      id: previous?.storage[index]?.id || `storage-${index}`,
      model,
      ...item,
    })),
    network: Object.entries(hbom.network).map(([model, item], index) => ({
      id: previous?.network[index]?.id || `network-${index}`,
      model,
      ...item,
    })),
  };
}

function parsePositiveInt(value: number): number | null {
  return Number.isFinite(value) && value >= 1 ? Math.floor(value) : null;
}

function parsePositiveNumber(value: number): number | null {
  return Number.isFinite(value) && value > 0 ? value : null;
}

function hbomFromDraft(draft: HardwareBomDraft, previousHBOM: HBOM): HBOM {
  const nextHBOM = emptyHBOM();
  nextHBOM.extra_info = previousHBOM.extra_info || {};

  for (const row of draft.cpus) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.cpus[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        cores_per_cpu: parsePositiveInt(row.cores_per_cpu) ?? 1,
        threads_per_core: parsePositiveInt(row.threads_per_core) ?? 1,
        architecture: row.architecture.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.gpus) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.gpus[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        memory_gb: parsePositiveNumber(row.memory_gb) ?? 0,
        interface: row.interface.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.memory) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.memory[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        capacity_gb: parsePositiveNumber(row.capacity_gb) ?? 0,
        memory_type: row.memory_type,
        speed_mt_s: parsePositiveInt(row.speed_mt_s) ?? 0,
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.storage) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.storage[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        capacity_gb: parsePositiveNumber(row.capacity_gb) ?? 0,
        storage_type: row.storage_type,
        interface: row.interface.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.network) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.network[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        bandwidth_gbps: parsePositiveNumber(row.bandwidth_gbps) ?? 0,
        network_type: row.network_type,
        interface: row.interface.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  return nextHBOM;
}

function hbomSyncKey(hbom: HBOM): string {
  return JSON.stringify(hbom);
}

export function PageHardwareBom({
  ree,
  locked,
  badges,
  log,
  running,
  runDone,
  ts,
  focusedField,
  onReeChange,
  onLockedChange,
  onGoService,
  onFocusedFieldChange,
  onRun,
  onCancel,
}: PageHardwareBomProps) {
  const focus = (key: string) => onFocusedFieldChange(key);
  const [draft, setDraft] = React.useState<HardwareBomDraft>(() =>
    draftFromHBOM(ree.hardware_description),
  );
  const pendingLocalHbomKeyRef = React.useRef<string | null>(null);

  useFocusScroll(focusedField);

  React.useEffect(() => {
    const incomingKey = hbomSyncKey(ree.hardware_description);
    if (pendingLocalHbomKeyRef.current === incomingKey) {
      pendingLocalHbomKeyRef.current = null;
      return;
    }
    setDraft((previous) => draftFromHBOM(ree.hardware_description, previous));
  }, [ree.hardware_description]);

  const updateDraft = (nextDraft: HardwareBomDraft) => {
    const nextHBOM = hbomFromDraft(nextDraft, ree.hardware_description);
    pendingLocalHbomKeyRef.current = hbomSyncKey(nextHBOM);
    setDraft(nextDraft);
    onReeChange({
      ...ree,
      hardware_description: nextHBOM,
    });
  };

  const cpuColumns: HardwareColumn<CPURow>[] = [
    {
      key: "model",
      label: "Device Model",
      width: "1.7fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) =>
            updateDraft({
              ...draft,
              cpus: draft.cpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, model: event.target.value } : item,
              ),
            })
          }
          onFocus={() => focus("hardware_description")}
          placeholder="Intel Core i9-14900K"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) =>
            updateDraft({
              ...draft,
              cpus: draft.cpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, vendor: event.target.value } : item,
              ),
            })
          }
          placeholder="Intel"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) =>
            updateDraft({
              ...draft,
              cpus: draft.cpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, quantity: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "cores",
      label: "Cores",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.cores_per_cpu}
          onChange={(event) =>
            updateDraft({
              ...draft,
              cpus: draft.cpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, cores_per_cpu: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="cores"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "threads",
      label: "Threads/Core",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.threads_per_core}
          onChange={(event) =>
            updateDraft({
              ...draft,
              cpus: draft.cpus.map((item, itemIndex) =>
                itemIndex === index
                  ? { ...item, threads_per_core: Number(event.target.value) }
                  : item,
              ),
            })
          }
          placeholder="threads/core"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "architecture",
      label: "Architecture",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.architecture}
          onChange={(event) =>
            updateDraft({
              ...draft,
              cpus: draft.cpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, architecture: event.target.value } : item,
              ),
            })
          }
          placeholder="x86_64"
          style={inp(locked)}
        />
      ),
    },
  ];

  const gpuColumns: HardwareColumn<GPURow>[] = [
    {
      key: "model",
      label: "Device Model",
      width: "1.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) =>
            updateDraft({
              ...draft,
              gpus: draft.gpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, model: event.target.value } : item,
              ),
            })
          }
          placeholder="NVIDIA A100-SXM4-40GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) =>
            updateDraft({
              ...draft,
              gpus: draft.gpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, vendor: event.target.value } : item,
              ),
            })
          }
          placeholder="NVIDIA"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) =>
            updateDraft({
              ...draft,
              gpus: draft.gpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, quantity: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "memory_gb",
      label: "Memory GB",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.memory_gb}
          onChange={(event) =>
            updateDraft({
              ...draft,
              gpus: draft.gpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, memory_gb: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="memory GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "interface",
      label: "Interface",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.interface}
          onChange={(event) =>
            updateDraft({
              ...draft,
              gpus: draft.gpus.map((item, itemIndex) =>
                itemIndex === index ? { ...item, interface: event.target.value } : item,
              ),
            })
          }
          placeholder="PCIe 4.0 x16"
          style={inp(locked)}
        />
      ),
    },
  ];

  const memoryColumns: HardwareColumn<MemoryRow>[] = [
    {
      key: "model",
      label: "Device Model",
      width: "1.7fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) =>
            updateDraft({
              ...draft,
              memory: draft.memory.map((item, itemIndex) =>
                itemIndex === index ? { ...item, model: event.target.value } : item,
              ),
            })
          }
          placeholder="DDR5 ECC 32GB DIMM"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) =>
            updateDraft({
              ...draft,
              memory: draft.memory.map((item, itemIndex) =>
                itemIndex === index ? { ...item, vendor: event.target.value } : item,
              ),
            })
          }
          placeholder="Samsung"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) =>
            updateDraft({
              ...draft,
              memory: draft.memory.map((item, itemIndex) =>
                itemIndex === index ? { ...item, quantity: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "capacity_gb",
      label: "Capacity GB",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.capacity_gb}
          onChange={(event) =>
            updateDraft({
              ...draft,
              memory: draft.memory.map((item, itemIndex) =>
                itemIndex === index ? { ...item, capacity_gb: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="capacity GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "memory_type",
      label: "Type",
      width: "1fr",
      render: (row, index) => (
        <select
          disabled={locked}
          value={row.memory_type}
          onChange={(event) =>
            updateDraft({
              ...draft,
              memory: draft.memory.map((item, itemIndex) =>
                itemIndex === index ? { ...item, memory_type: event.target.value } : item,
              ),
            })
          }
          style={selectInp(locked)}
        >
          {MEMORY_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "speed_mt_s",
      label: "Speed MT/s",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.speed_mt_s}
          onChange={(event) =>
            updateDraft({
              ...draft,
              memory: draft.memory.map((item, itemIndex) =>
                itemIndex === index ? { ...item, speed_mt_s: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="speed MT/s"
          style={inp(locked)}
        />
      ),
    },
  ];

  const storageColumns: HardwareColumn<StorageRow>[] = [
    {
      key: "model",
      label: "Device Model",
      width: "1.7fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) =>
            updateDraft({
              ...draft,
              storage: draft.storage.map((item, itemIndex) =>
                itemIndex === index ? { ...item, model: event.target.value } : item,
              ),
            })
          }
          placeholder="Samsung PM9A3"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) =>
            updateDraft({
              ...draft,
              storage: draft.storage.map((item, itemIndex) =>
                itemIndex === index ? { ...item, vendor: event.target.value } : item,
              ),
            })
          }
          placeholder="Samsung"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) =>
            updateDraft({
              ...draft,
              storage: draft.storage.map((item, itemIndex) =>
                itemIndex === index ? { ...item, quantity: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "capacity_gb",
      label: "Capacity GB",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.capacity_gb}
          onChange={(event) =>
            updateDraft({
              ...draft,
              storage: draft.storage.map((item, itemIndex) =>
                itemIndex === index ? { ...item, capacity_gb: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="capacity GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "storage_type",
      label: "Type",
      width: "1fr",
      render: (row, index) => (
        <select
          disabled={locked}
          value={row.storage_type}
          onChange={(event) =>
            updateDraft({
              ...draft,
              storage: draft.storage.map((item, itemIndex) =>
                itemIndex === index ? { ...item, storage_type: event.target.value } : item,
              ),
            })
          }
          style={selectInp(locked)}
        >
          {STORAGE_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "interface",
      label: "Interface",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.interface}
          onChange={(event) =>
            updateDraft({
              ...draft,
              storage: draft.storage.map((item, itemIndex) =>
                itemIndex === index ? { ...item, interface: event.target.value } : item,
              ),
            })
          }
          placeholder="PCIe 4.0 x4"
          style={inp(locked)}
        />
      ),
    },
  ];

  const networkColumns: HardwareColumn<NetworkRow>[] = [
    {
      key: "model",
      label: "Device Model",
      width: "1.6fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) =>
            updateDraft({
              ...draft,
              network: draft.network.map((item, itemIndex) =>
                itemIndex === index ? { ...item, model: event.target.value } : item,
              ),
            })
          }
          placeholder="ConnectX-6"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) =>
            updateDraft({
              ...draft,
              network: draft.network.map((item, itemIndex) =>
                itemIndex === index ? { ...item, vendor: event.target.value } : item,
              ),
            })
          }
          placeholder="NVIDIA"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) =>
            updateDraft({
              ...draft,
              network: draft.network.map((item, itemIndex) =>
                itemIndex === index ? { ...item, quantity: Number(event.target.value) } : item,
              ),
            })
          }
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "bandwidth_gbps",
      label: "Bandwidth Gbps",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.bandwidth_gbps}
          onChange={(event) =>
            updateDraft({
              ...draft,
              network: draft.network.map((item, itemIndex) =>
                itemIndex === index
                  ? { ...item, bandwidth_gbps: Number(event.target.value) }
                  : item,
              ),
            })
          }
          placeholder="bandwidth"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "network_type",
      label: "Type",
      width: "1fr",
      render: (row, index) => (
        <select
          disabled={locked}
          value={row.network_type}
          onChange={(event) =>
            updateDraft({
              ...draft,
              network: draft.network.map((item, itemIndex) =>
                itemIndex === index ? { ...item, network_type: event.target.value } : item,
              ),
            })
          }
          style={selectInp(locked)}
        >
          {NETWORK_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "interface",
      label: "Interface",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.interface}
          onChange={(event) =>
            updateDraft({
              ...draft,
              network: draft.network.map((item, itemIndex) =>
                itemIndex === index ? { ...item, interface: event.target.value } : item,
              ),
            })
          }
          placeholder="PCIe 4.0 x8"
          style={inp(locked)}
        />
      ),
    },
  ];

  return (
    <div style={S_WORKFLOW_PAGE_ROOT}>
      <WorkflowPageHeader
        color="#0f766e"
        icon={Ic.chip(18)}
        title="Create Hardware BOM"
        subtitle="Document the machine assumptions that matter today and can later expand to remote targets"
        tips={[
          "Each category is keyed by device model, matching the structured HBOM format stored in the REE draft.",
          "Only the device model is required. Other fields can stay at their defaults and will persist immediately.",
          "Use Profile This Machine to prefill the table, then adjust any rows manually before moving on.",
        ]}
        rightAction={
          locked ? (
            <button
              type="button"
              onClick={() => onLockedChange(false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                ...workflowToneSurfaceStyle("warn"),
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                fontFamily: F.sans,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {Ic.unlock(13)} Unlock fields
            </button>
          ) : null
        }
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_PAGE_MAIN_SCROLL}>
          <div style={S_WORKFLOW_PAGE_MAIN_COL}>
            <FieldSection
              title="CPU"
              icon={Ic.chip()}
              subtitle="processor packages and topology"
              filledCount={draft.cpus.length}
              totalCount={draft.cpus.length}
            >
              <FieldRow
                fieldKey="hardware_description"
                locked={locked}
                onFocus={() => focus("hardware_description")}
                active={focusedField === "hardware_description"}
              >
                <div style={{ padding: "12px 0" }}>
                  <HardwareCardSection
                    title="CPUs"
                    rows={draft.cpus}
                    columns={cpuColumns}
                    locked={locked}
                    onRemove={(index) =>
                      updateDraft({
                        ...draft,
                        cpus: draft.cpus.filter((_, itemIndex) => itemIndex !== index),
                      })
                    }
                    onAdd={() => updateDraft({ ...draft, cpus: [...draft.cpus, newCpuRow()] })}
                    addLabel="Add CPU"
                  />
                </div>
              </FieldRow>
            </FieldSection>

            <FieldSection
              title="GPU"
              icon={Ic.chip()}
              subtitle="accelerators and graphics devices"
              filledCount={draft.gpus.length}
              totalCount={draft.gpus.length}
            >
              <FieldRow
                fieldKey="hardware_description"
                locked={locked}
                onFocus={() => focus("hardware_description")}
                active={focusedField === "hardware_description"}
              >
                <div style={{ padding: "12px 0" }}>
                  <HardwareCardSection
                    title="GPUs"
                    rows={draft.gpus}
                    columns={gpuColumns}
                    locked={locked}
                    onRemove={(index) =>
                      updateDraft({
                        ...draft,
                        gpus: draft.gpus.filter((_, itemIndex) => itemIndex !== index),
                      })
                    }
                    onAdd={() => updateDraft({ ...draft, gpus: [...draft.gpus, newGpuRow()] })}
                    addLabel="Add GPU"
                  />
                </div>
              </FieldRow>
            </FieldSection>

            <FieldSection
              title="Memory"
              icon={Ic.chip()}
              subtitle="modules and aggregate RAM assumptions"
              filledCount={draft.memory.length}
              totalCount={draft.memory.length}
            >
              <FieldRow
                fieldKey="hardware_description"
                locked={locked}
                onFocus={() => focus("hardware_description")}
                active={focusedField === "hardware_description"}
              >
                <div style={{ padding: "12px 0" }}>
                  <HardwareCardSection
                    title="Memory"
                    rows={draft.memory}
                    columns={memoryColumns}
                    locked={locked}
                    onRemove={(index) =>
                      updateDraft({
                        ...draft,
                        memory: draft.memory.filter((_, itemIndex) => itemIndex !== index),
                      })
                    }
                    onAdd={() =>
                      updateDraft({ ...draft, memory: [...draft.memory, newMemoryRow()] })
                    }
                    addLabel="Add memory"
                  />
                </div>
              </FieldRow>
            </FieldSection>

            <FieldSection
              title="Storage"
              icon={Ic.chip()}
              subtitle="disks, SSDs, and runtime capacity"
              filledCount={draft.storage.length}
              totalCount={draft.storage.length}
            >
              <FieldRow
                fieldKey="hardware_description"
                locked={locked}
                onFocus={() => focus("hardware_description")}
                active={focusedField === "hardware_description"}
              >
                <div style={{ padding: "12px 0" }}>
                  <HardwareCardSection
                    title="Storage"
                    rows={draft.storage}
                    columns={storageColumns}
                    locked={locked}
                    onRemove={(index) =>
                      updateDraft({
                        ...draft,
                        storage: draft.storage.filter((_, itemIndex) => itemIndex !== index),
                      })
                    }
                    onAdd={() =>
                      updateDraft({ ...draft, storage: [...draft.storage, newStorageRow()] })
                    }
                    addLabel="Add storage"
                  />
                </div>
              </FieldRow>
            </FieldSection>

            <FieldSection
              title="Network"
              icon={Ic.chip()}
              subtitle="host interfaces and bandwidth"
              filledCount={draft.network.length}
              totalCount={draft.network.length}
            >
              <FieldRow
                fieldKey="hardware_description"
                locked={locked}
                onFocus={() => focus("hardware_description")}
                active={focusedField === "hardware_description"}
              >
                <div style={{ padding: "12px 0" }}>
                  <HardwareCardSection
                    title="Network"
                    rows={draft.network}
                    columns={networkColumns}
                    locked={locked}
                    onRemove={(index) =>
                      updateDraft({
                        ...draft,
                        network: draft.network.filter((_, itemIndex) => itemIndex !== index),
                      })
                    }
                    onAdd={() =>
                      updateDraft({ ...draft, network: [...draft.network, newNetworkRow()] })
                    }
                    addLabel="Add network"
                  />
                </div>
              </FieldRow>
            </FieldSection>

            <ServiceActionSection
              color="#0f766e"
              running={running}
              runDone={runDone}
              disabled={running}
              idleLabel="Profile This Machine"
              runningLabel="Profiling…"
              doneLabel="Re-profile Machine"
              helperText="Detects local CPU, GPU, memory, storage, and network details, then fills the HBOM table."
              onCancel={() => onCancel?.("hbom")}
              onRun={() => onRun("hbom", {})}
            />

            <WorkflowLogSection
              log={log}
              running={running}
              title={ts ? "Machine profiling logs" : "Profiling logs"}
            />

            <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
              <NextStepNudge stepKey="hbom" badges={badges} onGo={onGoService} />
            </div>
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["hardware_description"]}
          focusedField={focusedField}
          onClear={() => onFocusedFieldChange(null)}
        />
      </div>
    </div>
  );
}
