import {
  type DependencyGroup,
  STATUS_META,
  tallyByStatus,
} from "@core/evaluate/dependencyPresentation";
import { C, hoverBg, hoverBorderColor, hoverIf } from "@shell/ui/theme/theme";
import { actionBtn } from "./shared";

interface DependencySummaryFiltersProps {
  depGroups: DependencyGroup[];
  filter: string;
  onFilter: (next: string) => void;
}

export function DependencySummaryFilters({
  depGroups,
  filter,
  onFilter,
}: DependencySummaryFiltersProps) {
  const tally = tallyByStatus(depGroups.flatMap((group) => group.packages));

  return (
    <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
      {[
        {
          key: "all",
          label: `${tally.total} total`,
          color: C.textMid,
          bg: C.surfaceAlt,
          border: C.border,
        },
        { key: "locked", ...STATUS_META.locked, label: `${tally.locked} locked` },
        { key: "pinned", ...STATUS_META.pinned, label: `${tally.pinned} pinned` },
        { key: "ranged", ...STATUS_META.ranged, label: `${tally.ranged} range` },
        { key: "unpinned", ...STATUS_META.unpinned, label: `${tally.unpinned} unpinned` },
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
