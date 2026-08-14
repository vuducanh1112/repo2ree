import type { ArchiveRepo } from "@core/ree-steps/stepTypes";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import { archiveTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "../ArchivePage.module.css";

interface ArchiveRepoSummaryCardProps {
  repo: ArchiveRepo;
  assignedId?: string;
}

export function ArchiveRepoSummaryCard({ repo, assignedId }: ArchiveRepoSummaryCardProps) {
  const tone = archiveTone(repo.key);
  return (
    <Surface spacing="flush" vars={{ "--archive-tint": tone }}>
      <div className={styles.summaryHead}>
        <span aria-hidden className={styles.accentBar} />
        <span className={styles.repoName}>{repo.label}</span>
        <a href={repo.url} target="_blank" rel="noreferrer" className={styles.repoLink}>
          {Ic.link(11)} {repo.url.replace("https://", "")}
        </a>
      </div>

      <p className={styles.repoDesc}>{repo.desc}</p>

      <div
        className={styles.identifier}
        data-assigned={assignedId ? true : undefined}
        style={cssVars({ "--archive-tint": tone })}
      >
        <span className={styles.identifierKind}>{repo.idLabel}</span>
        <span className={styles.identifierValue}>{assignedId || repo.idPlaceholder}</span>
        {assignedId && (
          <Badge tint={{ line: tone, wash: "var(--surface-control)" }} icon={Ic.check(10)}>
            assigned
          </Badge>
        )}
      </div>
    </Surface>
  );
}
