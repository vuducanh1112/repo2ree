import type { DependencyGroup } from "@core/evaluate/dependencyPresentation";
import { useState } from "react";
import { DependencyGroupCard } from "./DependencyGroupCard";
import { DependencySummaryFilters } from "./DependencySummaryFilters";

interface DependencyPanelProps {
  depGroups: DependencyGroup[];
}
export function DependencyPanel({ depGroups }: DependencyPanelProps) {
  const [openGroups, setOpenGroups] = useState(() =>
    Object.fromEntries(depGroups.map((g) => [g.path, true])),
  );
  const [filter, setFilter] = useState("all");

  const toggle = (path: string) => setOpenGroups((o) => ({ ...o, [path]: !o[path] }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, minHeight: 0 }}>
      <DependencySummaryFilters depGroups={depGroups} filter={filter} onFilter={setFilter} />

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {depGroups.map((group) => (
          <DependencyGroupCard
            key={group.path}
            group={group}
            filter={filter}
            isOpen={openGroups[group.path] !== false}
            onToggle={() => toggle(group.path)}
          />
        ))}
      </div>
    </div>
  );
}
