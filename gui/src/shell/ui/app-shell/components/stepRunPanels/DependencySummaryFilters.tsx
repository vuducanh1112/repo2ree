import {
  type DependencyGroup,
  STATUS_LABEL,
  tallyByStatus,
} from "@core/evaluate/dependencyPresentation";
import type { DependencyStatus } from "@core/evaluate/Threat";
import { dependencyStatusTone } from "@shell/ui/theme/appearance";
import { C, hoverBg, hoverBorderColor, hoverIf } from "@shell/ui/theme/theme";
import { actionBtn } from "./shared";

interface DependencySummaryFiltersProps {
  depGroups: DependencyGroup[];
  filter: string;
  onFilter: (next: string) => void;
}

/** One pinning-status chip: the tone comes from the status, the wording from
 * core's label map, and the count from the tally. */
function statusFilter(status: DependencyStatus, count: number) {
  return {
    key: status,
    label: `${count} ${STATUS_LABEL[status]}`,
    color: dependencyStatusTone(status),
    bg: dependencyStatusTone(status, "wash"),
    border: dependencyStatusTone(status, "edge"),
  };
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
        ...(["locked", "pinned", "ranged", "unpinned"] as const).map((status) =>
          statusFilter(status, tally[status]),
        ),
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
