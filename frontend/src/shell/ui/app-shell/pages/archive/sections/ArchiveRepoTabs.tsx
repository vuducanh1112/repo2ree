import type { Badges } from "@core/ree/ReeTypes";
import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgSegmentedTab } from "@shell/ui/theme/lightGlassTheme";

interface ArchiveRepoTabsProps {
  repositories: ArchiveRepo[];
  activeRepo: string;
  badges: Badges;
  onSelect: (key: string) => void;
}

export function ArchiveRepoTabs({
  repositories,
  activeRepo,
  badges,
  onSelect,
}: ArchiveRepoTabsProps) {
  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 22, flexWrap: "wrap" }}>
      {repositories.map((archiveRepo) => {
        const isActive = activeRepo === archiveRepo.key;
        const isDone = !!badges[archiveRepo.key];
        return (
          <button
            type="button"
            key={archiveRepo.key}
            onClick={() => onSelect(archiveRepo.key)}
            style={{
              ...lgSegmentedTab(isActive),
              flex: 1,
              minWidth: 140,
              justifyContent: "center",
              ...(isActive
                ? {
                    border: `1px solid ${archiveRepo.color}99`,
                    color: archiveRepo.color,
                    boxShadow: `0 12px 26px ${archiveRepo.color}26`,
                  }
                : {}),
            }}
          >
            {isDone && (
              <span style={{ color: archiveRepo.color, display: "flex" }}>{Ic.check(13)}</span>
            )}
            {archiveRepo.label}
          </button>
        );
      })}
    </div>
  );
}
