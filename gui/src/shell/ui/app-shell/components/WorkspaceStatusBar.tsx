import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ReeFile } from "@core/ree/ReeTypes";
import type { ReviewStepKey } from "@core/reviews/reviewDag";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { ReactNode } from "react";
import { Ic } from "../../shared/components/Icon";
import { type AuthoringWorkflowModel, AuthoringWorkflowPanel } from "../canvas/AuthoringConsole";
import { ReviewStrip } from "../canvas/review/ReviewStrip";
import type { ReviewWorkflowModel } from "../canvas/review/useReviewWorkflowModel";
import { useFileConsoleTrees } from "../pages/files/useFileConsoleTrees";
import styles from "./WorkspaceStatusBar.module.css";

export type WorkflowMode = "authoring" | "review";

interface WorkspaceStatusBarProps {
  page: AppShellPage;
  /** Owned by the shell, so the canvas highlights the same next step this does. */
  authoring: AuthoringWorkflowModel;
  /** Owned by the shell too: the strip and the evidence drawer are one attempt. */
  review: ReviewWorkflowModel;
  mode: WorkflowMode;
  onModeChange: (mode: WorkflowMode) => void;
  /** The review step whose evidence the drawer is showing, if any. */
  openReviewStep: ReviewStepKey | null;
  onOpenReviewStep: (step: ReviewStepKey) => void;
  workspaceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  receiptCount: number;
  filesOpen: boolean;
  receiptsOpen: boolean;
  onNavigate: (page: AppShellPage) => void;
  onFilesOpenChange: (open: boolean) => void;
  onReceiptsOpenChange: (open: boolean) => void;
}

/** Persistent workflow and evidence navigation above the live canvas. */
export function WorkspaceStatusBar({
  page,
  authoring,
  review,
  mode,
  onModeChange,
  openReviewStep,
  onOpenReviewStep,
  workspaceFiles,
  reeFiles,
  receiptCount,
  filesOpen,
  receiptsOpen,
  onNavigate,
  onFilesOpenChange,
  onReceiptsOpenChange,
}: WorkspaceStatusBarProps) {
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
            onClick={() => onModeChange(reviewing ? "authoring" : "review")}
          >
            <span data-active={!reviewing || undefined}>
              Authoring{" "}
              <small>
                {authoring.complete}/{authoring.steps.length}
              </small>
            </span>
            <span data-active={reviewing || undefined}>
              Review <small>{review.complete}/4</small>
            </span>
          </button>
        </div>

        {/* Both workflows stand on the same strip: the bar's height and layout
         * are the same whichever one is showing. */}
        <div className={styles.body}>
          {reviewing ? (
            <ReviewStrip model={review} openStep={openReviewStep} onOpenStep={onOpenReviewStep} />
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
