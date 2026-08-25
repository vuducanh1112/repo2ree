import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { type ReactNode, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { type AuthoringWorkflowModel, AuthoringWorkflowPanel } from "../canvas/AuthoringConsole";
import { type ReviewWorkflowHeader, ReviewWorkflowPanel } from "../canvas/ReviewConsole";
import { useFileConsoleTrees } from "../pages/files/useFileConsoleTrees";
import styles from "./WorkspaceStatusBar.module.css";

type WorkflowMode = "authoring" | "review";

interface WorkspaceStatusBarProps {
  page: AppShellPage;
  /** Owned by the shell, so the canvas highlights the same next step this does. */
  authoring: AuthoringWorkflowModel;
  experiments: readonly ReeExperiment[];
  workspaceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  receiptCount: number;
  filesOpen: boolean;
  receiptsOpen: boolean;
  onNavigate: (page: AppShellPage) => void;
  onFilesOpenChange: (open: boolean) => void;
  onReceiptsOpenChange: (open: boolean) => void;
}

const INITIAL_REVIEW_HEADER: ReviewWorkflowHeader = {
  complete: 0,
};

/** Persistent workflow and evidence navigation above the live canvas. */
export function WorkspaceStatusBar({
  page,
  authoring,
  experiments,
  workspaceFiles,
  reeFiles,
  receiptCount,
  filesOpen,
  receiptsOpen,
  onNavigate,
  onFilesOpenChange,
  onReceiptsOpenChange,
}: WorkspaceStatusBarProps) {
  const [mode, setMode] = useState<WorkflowMode>("authoring");
  const [reviewHeader, setReviewHeader] = useState(INITIAL_REVIEW_HEADER);
  const { workspaceFileCount, reeFileCount } = useFileConsoleTrees(workspaceFiles, reeFiles);
  const fileCount = workspaceFileCount + reeFileCount;
  const reviewing = mode === "review";

  return (
    <section aria-label="Workspace status" className={styles.bar}>
      <UtilityButton
        label="Files"
        detail={fileCount > 0 ? `${workspaceFileCount} workspace · ${reeFileCount} REE` : "Empty"}
        icon={Ic.files(16)}
        active={filesOpen}
        onClick={() => onFilesOpenChange(!filesOpen)}
      />

      <div className={styles.workflow}>
        <div className={styles.workflowHeader}>
          <button
            type="button"
            aria-label={`Switch to ${reviewing ? "authoring" : "review"} workflow`}
            aria-pressed={reviewing}
            className={styles.modeToggle}
            onClick={() => setMode(reviewing ? "authoring" : "review")}
          >
            <span data-active={!reviewing || undefined}>
              Authoring{" "}
              <small>
                {authoring.complete}/{authoring.steps.length}
              </small>
            </span>
            <span data-active={reviewing || undefined}>
              Review <small>{reviewHeader.complete}/4</small>
            </span>
          </button>
        </div>

        <div className={reviewing ? styles.reviewBody : styles.authoringBody}>
          {reviewing ? (
            <ReviewWorkflowPanel experiments={experiments} onHeaderChange={setReviewHeader} />
          ) : (
            <AuthoringWorkflowPanel page={page} model={authoring} onNavigate={onNavigate} />
          )}
        </div>
      </div>

      <UtilityButton
        label="Receipts"
        detail={receiptCount === 0 ? "No evidence" : `${receiptCount} recorded`}
        icon={Ic.shield(16)}
        active={receiptsOpen}
        onClick={() => {
          const opening = !receiptsOpen;
          if (opening) onNavigate(PAGE.CANVAS);
          onReceiptsOpenChange(opening);
        }}
      />
    </section>
  );
}

function UtilityButton({
  label,
  detail,
  icon,
  active,
  onClick,
}: {
  label: string;
  detail: string;
  icon: ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className={styles.utility} aria-pressed={active} onClick={onClick}>
      <span aria-hidden className={styles.utilityIcon}>
        {icon}
      </span>
      <span className={styles.utilityCopy}>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
      <span aria-hidden className={styles.statusDot} data-on={active || undefined} />
    </button>
  );
}
