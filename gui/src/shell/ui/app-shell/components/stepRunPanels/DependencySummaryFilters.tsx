import {
  type DependencyGroup,
  STATUS_LABEL,
  tallyByStatus,
} from "@core/evaluate/dependencyPresentation";
import type { DependencyStatus } from "@core/evaluate/Threat";
import { dependencyStatusTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "./DependencyPanel.module.css";

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
    ink: dependencyStatusTone(status),
    wash: dependencyStatusTone(status, "wash"),
    edge: dependencyStatusTone(status, "edge"),
  };
}

export function DependencySummaryFilters({
  depGroups,
  filter,
  onFilter,
}: DependencySummaryFiltersProps) {
  const tally = tallyByStatus(depGroups.flatMap((group) => group.packages));

  return (
    <div className={styles.filters}>
      {[
        {
          key: "all",
          label: `${tally.total} total`,
          ink: undefined,
          wash: undefined,
          edge: undefined,
        },
        ...(["locked", "pinned", "ranged", "unpinned"] as const).map((status) =>
          statusFilter(status, tally[status]),
        ),
      ].map((summaryFilter) => (
        <button
          type="button"
          key={summaryFilter.key}
          onClick={() => onFilter(summaryFilter.key)}
          aria-pressed={filter === summaryFilter.key}
          className={styles.filter}
          style={cssVars({
            "--filter-ink": summaryFilter.ink,
            "--filter-wash": summaryFilter.wash,
            "--filter-edge": summaryFilter.edge,
          })}
        >
          {summaryFilter.label}
        </button>
      ))}
    </div>
  );
}
