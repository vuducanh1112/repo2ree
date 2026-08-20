import styles from "./AppShellContent.module.css";
import { ArchivePageContainer } from "./pages/pageContainers/ArchivePageContainer";
import {
  ExperimentsPageContainer,
  HardwareBomPageContainer,
  MetadataPageContainer,
  StepPageContainer,
} from "./pages/pageContainers/DockedPageContainers";
import type { AppShellPageContainerProps } from "./pages/pageContainers/shared";

export function AppShellContent(props: AppShellPageContainerProps) {
  return (
    <div className={styles.main}>
      <div aria-hidden className={styles.backdrop}>
        <div className={styles.blob} data-place="left" />
        <div className={styles.blob} data-place="right" />
        <div className={styles.blob} data-place="center" />
      </div>
      <div className={styles.inner}>
        <MetadataPageContainer {...props} />
        <ExperimentsPageContainer {...props} />
        <HardwareBomPageContainer {...props} />
        <StepPageContainer {...props} />
        <ArchivePageContainer {...props} />
      </div>
    </div>
  );
}
