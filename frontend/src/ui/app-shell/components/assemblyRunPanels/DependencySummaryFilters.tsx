import type { DepGroup } from "../../../../core/ree-assembly/assemblyDependencyAnalysis";
import { PIN_META } from "../../../../core/ree-assembly/assemblyDependencyAnalysis";
import { C, hoverBg, hoverBorderColor, hoverIf } from "../../../theme/theme";
import { actionBtn } from "./shared";

interface DependencySummaryFiltersProps {
  depGroups: DepGroup[];
  filter: string;
  onFilter: (next: string) => void;
}

export function DependencySummaryFilters({
  depGroups,
  filter,
  onFilter,
}: DependencySummaryFiltersProps) {
  const totalPkgs = depGroups.reduce((sum, group) => sum + group.packages.length, 0);
  const pinnedCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "exact").length,
    0,
  );
  const rangeCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "range").length,
    0,
  );
  const noneCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "none").length,
    0,
  );

  return (
    <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
      {[
        {
          key: "all",
          label: `${totalPkgs} total`,
          color: C.textMid,
          bg: C.surfaceAlt,
          border: C.border,
        },
        { key: "exact", ...PIN_META.exact, label: `${pinnedCount} pinned` },
        { key: "range", ...PIN_META.range, label: `${rangeCount} range` },
        { key: "none", ...PIN_META.none, label: `${noneCount} unpinned` },
      ].map((summaryFilter) => (
        <button
          type="button"
          key={summaryFilter.key}
          onClick={() => onFilter(summaryFilter.key)}
          style={{
            ...actionBtn({
              fontSize: 11,
              borderRadius: 99,
              padding: "3px 10px",
              transition: "all 0.12s",
            }),
            color: summaryFilter.color,
            background: filter === summaryFilter.key ? summaryFilter.bg : "transparent",
            border: `1.5px solid ${filter === summaryFilter.key ? summaryFilter.border : C.border}`,
            cursor: "pointer",
          }}
          {...hoverIf(filter !== summaryFilter.key, hoverBg(summaryFilter.bg, "transparent"))}
          {...hoverIf(
            filter !== summaryFilter.key,
            hoverBorderColor(summaryFilter.border, C.border),
          )}
        >
          {summaryFilter.label}
        </button>
      ))}
    </div>
  );
}
