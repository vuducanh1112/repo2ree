import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { Suspense } from "react";
import styles from "./AppShellContent.module.css";
import { ArchivePageContainer } from "./pages/pageContainers/ArchivePageContainer";
import type { AppShellContentProps } from "./pages/pageContainers/controllerContracts";
import {
  ExperimentsPageContainer,
  HardwareBomPageContainer,
  MetadataPageContainer,
  StepPageContainer,
} from "./pages/pageContainers/DockedPageContainers";

export function AppShellContent({ page, ...props }: AppShellContentProps) {
  return (
    <div className={styles.main}>
      <div aria-hidden className={styles.backdrop}>
        <div className={styles.blob} data-place="left" />
        <div className={styles.blob} data-place="right" />
        <div className={styles.blob} data-place="center" />
      </div>
      <div className={styles.inner}>
        <Suspense
          fallback={
            <div className={styles.pageLoading} role="status" aria-live="polite">
              <span className={styles.pageLoadingIndicator} aria-hidden />
              <span>Loading workspace page…</span>
            </div>
          }
        >
          {activePageContent(page, props)}
        </Suspense>
      </div>
    </div>
  );
}

function activePageContent(page: AppShellPage, props: Omit<AppShellContentProps, "page">) {
  const { ree, reeIntent, workspaceRemote, stepRuns, uiChrome, currentReeFiles, commands } = props;
  switch (page) {
    case PAGE.METADATA:
      return (
        <MetadataPageContainer
          reeIntent={reeIntent}
          stepRuns={stepRuns}
          uiChrome={uiChrome}
          commands={commands}
        />
      );
    case PAGE.EXPERIMENTS:
      return (
        <ExperimentsPageContainer
          reeIntent={reeIntent}
          stepRuns={stepRuns}
          uiChrome={uiChrome}
          workspaceRemote={workspaceRemote}
          commands={commands}
        />
      );
    case PAGE.HBOM:
      return (
        <HardwareBomPageContainer
          ree={ree}
          stepRuns={stepRuns}
          uiChrome={uiChrome}
          commands={commands}
        />
      );
    case PAGE.ARCHIVE:
      return (
        <ArchivePageContainer
          ree={ree}
          workspaceRemote={workspaceRemote}
          stepRuns={stepRuns}
          commands={commands}
        />
      );
    case PAGE.EVALUATE:
    case PAGE.BUILD:
    case PAGE.SBOM:
    case PAGE.ACTIVATION:
      return (
        <StepPageContainer
          page={page}
          ree={ree}
          workspaceRemote={workspaceRemote}
          stepRuns={stepRuns}
          uiChrome={uiChrome}
          currentReeFiles={currentReeFiles}
          commands={commands}
        />
      );
    default:
      return null;
  }
}
