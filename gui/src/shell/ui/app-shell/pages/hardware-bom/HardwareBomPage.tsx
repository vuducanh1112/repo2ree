import { PAGE } from "@core/app-shell/pages";
import {
  type HardwareBomDraft,
  newCpuRow,
  newGpuRow,
  newMemoryRow,
  newNetworkRow,
  newStorageRow,
} from "@core/hbom/hardwareBomDraft";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import { useFocusScroll } from "@shell/ui/shared/hooks/useFocusScroll";
import { stageTone } from "@shell/ui/theme/appearance";
import { useState } from "react";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPageShell, GlassPanel, GlassSectionBody } from "../../components/GlassPageShell";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { RunActionButton } from "../../components/RunActionButton";
import { useHardwareBomDraft } from "../../hooks/useHardwareBomDraft";
import type { PageHardwareBomProps } from "../sharedStepUi";
import styles from "./HardwareBomPage.module.css";
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

const HBOM_ACCENT = stageTone(PAGE.HBOM);

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

  const focusHardwareDescription = () => onFocusedFieldChange("hardwareDescription");

  const cpuColumns = createCpuColumns({
    locked,
    onFocusHardwareDescription: focusHardwareDescription,
    patchCpuRow: (index, patch) => patchRow("cpus", index, patch),
  });
  const gpuColumns = createGpuColumns({
    locked,
    patchGpuRow: (index, patch) => patchRow("gpus", index, patch),
  });
  const memoryColumns = createMemoryColumns({
    locked,
    patchMemoryRow: (index, patch) => patchRow("memory", index, patch),
  });
  const storageColumns = createStorageColumns({
    locked,
    patchStorageRow: (index, patch) => patchRow("storage", index, patch),
  });
  const networkColumns = createNetworkColumns({
    locked,
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
      <Badge tone="info">
        {totalRows} {totalRows === 1 ? "device" : "devices"}
      </Badge>
      <Badge tone={statusReady ? "success" : "warning"}>{statusLabel}</Badge>
    </>
  );

  const runDisabled = running || locked;
  const runLabel = running ? "Profiling…" : runDone ? "Re-profile" : "Profile machine";

  const headerRight = (
    <div className={styles.headerActions}>
      {running && onCancel && (
        <Button
          variant="danger"
          size="small"
          aria-label="Cancel profiling"
          onClick={() => onCancel("hbom")}
        >
          {Ic.x(13)}
        </Button>
      )}
      <RunActionButton
        label={runLabel}
        running={running}
        disabled={runDisabled}
        iconSize={13}
        variant="accent"
        tint={HBOM_ACCENT}
        onRun={() => onRun("hbom", {})}
      />
    </div>
  );

  return (
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={Ic.cpu(24)}
        tint={HBOM_ACCENT}
        title="Hardware BOM"
        subtitle="Document the machine assumptions that matter today — expand later to remote targets."
        badges={headerBadges}
        right={headerRight}
      />

      <GlassPanel clipped>
        <GlassSectionBody>
          <GlassSectionHeader
            icon={Ic.layers(19)}
            tint={HBOM_ACCENT}
            title="Hardware Inventory"
            subtitle="Switch categories below — only the device model is required per row."
          />

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
        </GlassSectionBody>

        <GlassPanelFooter>
          {totalRows === 0
            ? "Run Profile This Machine to prefill the tables, then adjust as needed."
            : `${totalRows} ${totalRows === 1 ? "device" : "devices"} across ${categoriesWithRows} of 5 categories.`}
        </GlassPanelFooter>
      </GlassPanel>
    </GlassPageShell>
  );
}
