import type { Badges } from "@core/ree/ReeTypes";
import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { Ic } from "@shell/ui/shared/components/Icon";
import { SegmentedControl } from "@shell/ui/shared/components/SegmentedControl";
import styles from "../ArchivePage.module.css";

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
    <div className={styles.tabs}>
      <SegmentedControl
        label="Archive"
        stretch
        value={activeRepo}
        segments={repositories.map((archiveRepo) => ({
          key: archiveRepo.key,
          label: archiveRepo.label,
          icon: badges[archiveRepo.key] ? Ic.check(13) : undefined,
        }))}
        onChange={onSelect}
      />
    </div>
  );
}
