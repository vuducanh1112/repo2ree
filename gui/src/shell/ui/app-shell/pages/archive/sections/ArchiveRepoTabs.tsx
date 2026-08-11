import type { Badges } from "@core/ree/ReeTypes";
import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { Ic } from "@shell/ui/shared/components/Icon";
import { archiveTone, translucent } from "@shell/ui/theme/appearance";
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
                    border: `1px solid ${translucent(archiveTone(archiveRepo.key), 60)}`,
                    color: archiveTone(archiveRepo.key),
                    boxShadow: `0 12px 26px ${translucent(archiveTone(archiveRepo.key), 15)}`,
                  }
                : {}),
            }}
          >
            {isDone && (
              <span style={{ color: archiveTone(archiveRepo.key), display: "flex" }}>
                {Ic.check(13)}
              </span>
            )}
            {archiveRepo.label}
          </button>
        );
      })}
    </div>
  );
}
