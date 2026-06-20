import {
  type HardwareBomDraft,
  newCpuRow,
  newGpuRow,
  newMemoryRow,
  newNetworkRow,
  newStorageRow,
} from "@core/hbom/hardwareBomDraft";
import { Ic } from "@shell/ui/shared/components/Icon";
import { useFocusScroll } from "@shell/ui/shared/hooks/useFocusScroll";
import {
  lgAccentActionButton,
  lgColors,
  lgGlassButton,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F, S_ACTION_BUTTON_BASE } from "@shell/ui/theme/theme";
import { useState } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { RunActionButton } from "../../components/RunActionButton";
import { useHardwareBomDraft } from "../../hooks/useHardwareBomDraft";
import type { PageHardwareBomProps } from "../sharedAssemblyUi";
import {
  type CategoryDescriptor,
  HardwareCategoryTabs,
  HardwareTableCard,
} from "./HardwareBomPageSections";
import {
  createCpuColumns,
  createGpuColumns,
  createMemoryColumns,
  createNetworkColumns,
  createStorageColumns,
} from "./hardwareBomColumns";
import { inp, selectInp } from "./hardwareBomPageHelpers";

const HBOM_ACCENT = "#0f766e";

function generateRowId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random()}`;
}

const CATEGORIES: CategoryDescriptor[] = [
  {
    key: "cpus",
    label: "CPUs",
    singular: "CPU",
    addLabel: "Add CPU",
    icon: Ic.cpu(15),
    subtitle: "Processor packages and topology",
  },
  {
    key: "gpus",
    label: "GPUs",
    singular: "GPU",
    addLabel: "Add GPU",
    icon: Ic.chip(15),
    subtitle: "Accelerators and graphics devices",
  },
  {
    key: "memory",
    label: "Memory",
    singular: "memory module",
    addLabel: "Add memory",
    icon: Ic.layers(15),
    subtitle: "Modules and aggregate RAM",
  },
  {
    key: "storage",
    label: "Storage",
    singular: "storage device",
    addLabel: "Add storage",
    icon: Ic.archive(15),
    subtitle: "Disks, SSDs, and runtime capacity",
  },
  {
    key: "network",
    label: "Network",
    singular: "network interface",
    addLabel: "Add network",
    icon: Ic.globe(15),
    subtitle: "Host interfaces and bandwidth",
  },
];

export function PageHardwareBom({
  ree: reeIntent,
  locked,
  badges: _badges,
  log,
  running,
  runDone,
  ts,
  focusedField,
  onReeSpecChange,
  onLockedChange,
  onFocusedFieldChange,
  onRun,
  onCancel,
}: PageHardwareBomProps) {
  const { draft, updateDraft } = useHardwareBomDraft({ ree: reeIntent, onReeSpecChange });
  const [activeCategory, setActiveCategory] = useState<CategoryDescriptor["key"]>("cpus");

  useFocusScroll(focusedField);

  const setRows = <K extends keyof HardwareBomDraft>(key: K, rows: HardwareBomDraft[K]) => {
    updateDraft({ ...draft, [key]: rows } as HardwareBomDraft);
  };

  const patchRow = <K extends keyof HardwareBomDraft>(
    key: K,
    index: number,
    patch: Partial<HardwareBomDraft[K][number]>,
  ) => {
    const rows = draft[key];
    const next = rows.map((row, rowIndex) =>
      rowIndex === index ? { ...row, ...patch } : row,
    ) as HardwareBomDraft[K];
    setRows(key, next);
  };

  const removeRow = <K extends keyof HardwareBomDraft>(key: K, index: number) => {
    const next = draft[key].filter((_, rowIndex) => rowIndex !== index) as HardwareBomDraft[K];
    setRows(key, next);
  };

  const focusHardwareDescription = () => onFocusedFieldChange("hardware_description");

  const cpuColumns = createCpuColumns({
    locked,
    inp,
    selectInp,
    onFocusHardwareDescription: focusHardwareDescription,
    patchCpuRow: (index, patch) => patchRow("cpus", index, patch),
  });
  const gpuColumns = createGpuColumns({
    locked,
    inp,
    selectInp,
    patchGpuRow: (index, patch) => patchRow("gpus", index, patch),
  });
  const memoryColumns = createMemoryColumns({
    locked,
    inp,
    selectInp,
    patchMemoryRow: (index, patch) => patchRow("memory", index, patch),
  });
  const storageColumns = createStorageColumns({
    locked,
    inp,
    selectInp,
    patchStorageRow: (index, patch) => patchRow("storage", index, patch),
  });
  const networkColumns = createNetworkColumns({
    locked,
    inp,
    selectInp,
    patchNetworkRow: (index, patch) => patchRow("network", index, patch),
  });

  const counts = {
    cpus: draft.cpus.length,
    gpus: draft.gpus.length,
    memory: draft.memory.length,
    storage: draft.storage.length,
    network: draft.network.length,
  } as const;
  const totalRows = counts.cpus + counts.gpus + counts.memory + counts.storage + counts.network;
  const categoriesWithRows = (Object.values(counts) as number[]).filter(
    (count) => count > 0,
  ).length;

  const statusReady = totalRows > 0;
  const statusLabel = running ? "Profiling" : statusReady ? "Recorded" : "Empty";

  const renderActiveCategory = () => {
    switch (activeCategory) {
      case "cpus":
        return (
          <HardwareTableCard
            category={CATEGORIES[0]}
            rows={draft.cpus}
            columns={cpuColumns}
            locked={locked}
            onAdd={() => setRows("cpus", [...draft.cpus, newCpuRow(generateRowId)])}
            onRemove={(index) => removeRow("cpus", index)}
          />
        );
      case "gpus":
        return (
          <HardwareTableCard
            category={CATEGORIES[1]}
            rows={draft.gpus}
            columns={gpuColumns}
            locked={locked}
            onAdd={() => setRows("gpus", [...draft.gpus, newGpuRow(generateRowId)])}
            onRemove={(index) => removeRow("gpus", index)}
          />
        );
      case "memory":
        return (
          <HardwareTableCard
            category={CATEGORIES[2]}
            rows={draft.memory}
            columns={memoryColumns}
            locked={locked}
            onAdd={() => setRows("memory", [...draft.memory, newMemoryRow(generateRowId)])}
            onRemove={(index) => removeRow("memory", index)}
          />
        );
      case "storage":
        return (
          <HardwareTableCard
            category={CATEGORIES[3]}
            rows={draft.storage}
            columns={storageColumns}
            locked={locked}
            onAdd={() => setRows("storage", [...draft.storage, newStorageRow(generateRowId)])}
            onRemove={(index) => removeRow("storage", index)}
          />
        );
      case "network":
        return (
          <HardwareTableCard
            category={CATEGORIES[4]}
            rows={draft.network}
            columns={networkColumns}
            locked={locked}
            onAdd={() => setRows("network", [...draft.network, newNetworkRow(generateRowId)])}
            onRemove={(index) => removeRow("network", index)}
          />
        );
    }
  };

  const headerBadges = (
    <>
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: lgColors.chipText,
          background: "rgba(239, 246, 255, 0.85)",
          border: "1px solid rgba(79, 70, 229, 0.28)",
          borderRadius: 99,
          padding: "3px 9px",
        }}
      >
        {totalRows} {totalRows === 1 ? "device" : "devices"}
      </span>
      <span style={lgStatusBadge(statusReady)}>{statusLabel}</span>
    </>
  );

  const runDisabled = running || locked;
  const runLabel = running ? "Profiling…" : runDone ? "Re-profile" : "Profile machine";

  const headerRight = (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
      {locked && (
        <button
          type="button"
          onClick={() => onLockedChange(false)}
          style={{
            ...lgGlassButton(),
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 12,
          }}
        >
          {Ic.unlock(13)} Unlock fields
        </button>
      )}
      {running && onCancel && (
        <button
          type="button"
          onClick={() => onCancel("hbom")}
          style={{
            ...S_ACTION_BUTTON_BASE,
            display: "flex",
            alignItems: "center",
            padding: "8px 10px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            color: lgColors.danger,
            background: "rgba(255, 241, 242, 0.82)",
            border: `1px solid ${lgColors.dangerBorder}`,
          }}
        >
          {Ic.x(13)}
        </button>
      )}
      <RunActionButton
        label={runLabel}
        running={running}
        disabled={runDisabled}
        iconSize={13}
        style={lgAccentActionButton(HBOM_ACCENT, runDisabled)}
        onRun={() => onRun("hbom", {})}
      />
    </div>
  );

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.cpu(24)}
          iconTint={{
            color: "#0f766e",
            border: "rgba(15, 118, 110, 0.32)",
            shadow: "rgba(15, 118, 110, 0.14)",
          }}
          title="Hardware BOM"
          subtitle="Document the machine assumptions that matter today — expand later to remote targets."
          badges={headerBadges}
          right={headerRight}
        />

        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <div style={lgStyles.sectionHeader}>
              <div
                style={{
                  ...lgStyles.sectionIcon,
                  color: "#0f766e",
                  border: "1px solid rgba(15, 118, 110, 0.28)",
                }}
              >
                {Ic.layers(19)}
              </div>
              <div>
                <h2 style={lgStyles.sectionTitle}>Hardware Inventory</h2>
                <div style={lgStyles.sectionSubtitle}>
                  Switch categories below — only the device model is required per row.
                </div>
              </div>
            </div>

            <HardwareCategoryTabs
              categories={CATEGORIES}
              counts={counts}
              activeKey={activeCategory}
              onSelect={setActiveCategory}
            />

            {renderActiveCategory()}

            <CollapsibleLogCard
              log={log}
              running={running}
              title={ts ? "Profiling log" : "Profiling logs"}
            />
          </div>

          <div style={lgStyles.footer}>
            <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
              {totalRows === 0
                ? "Run Profile This Machine to prefill the tables, then adjust as needed."
                : `${totalRows} ${totalRows === 1 ? "device" : "devices"} across ${categoriesWithRows} of 5 categories.`}
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}
