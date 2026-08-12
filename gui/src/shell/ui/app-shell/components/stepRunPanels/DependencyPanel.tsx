import type { DependencyGroup } from "@core/evaluate/dependencyPresentation";
import { useState } from "react";
import { DependencyGroupCard } from "./DependencyGroupCard";
import styles from "./DependencyPanel.module.css";
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
    <div className={styles.panel}>
      <DependencySummaryFilters depGroups={depGroups} filter={filter} onFilter={setFilter} />

      <div className={styles.groups}>
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
