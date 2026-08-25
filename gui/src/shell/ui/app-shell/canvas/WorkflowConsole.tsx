import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { type KeyboardEvent, useId, useRef, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";
import { AuthoringWorkflowPanel, useAuthoringWorkflowModel } from "./AuthoringConsole";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";
import { type ReviewWorkflowHeader, ReviewWorkflowPanel } from "./ReviewConsole";
import styles from "./WorkflowConsole.module.css";

type WorkflowMode = "authoring" | "review";

const INITIAL_REVIEW_HEADER: ReviewWorkflowHeader = {
  subtitle: "ready for source review",
  running: false,
  complete: 0,
};

interface WorkflowConsoleProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  badges: Badges;
  experiments: readonly ReeExperiment[];
  onNavigate: (page: AppShellPage) => void;
}

/** One workflow surface for authoring navigation and independent review. */
export function WorkflowConsole({
  page,
  ree,
  badges,
  experiments,
  onNavigate,
}: WorkflowConsoleProps) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<WorkflowMode>("authoring");
  const [reviewHeader, setReviewHeader] = useState(INITIAL_REVIEW_HEADER);
  const authoring = useAuthoringWorkflowModel(ree, badges);
  const authoringTab = useRef<HTMLButtonElement>(null);
  const reviewTab = useRef<HTMLButtonElement>(null);
  const id = useId();

  const reviewing = mode === "review";
  const subtitle = reviewing
    ? `Review · ${reviewHeader.subtitle}`
    : `Authoring · ${authoring.subtitle}`;
  const active = reviewing ? reviewHeader.running || reviewHeader.complete > 0 : authoring.active;

  const selectMode = (next: WorkflowMode, focus = false) => {
    setMode(next);
    if (focus) {
      const target = next === "authoring" ? authoringTab : reviewTab;
      target.current?.focus();
    }
  };

  const handleTabKey = (event: KeyboardEvent, current: WorkflowMode) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    selectMode(current === "authoring" ? "review" : "authoring", true);
  };

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={reviewing ? 720 : 1400}
      widthCollapsed={360}
      className={hud.workflowPlacement}
      icon={reviewing ? Ic.refresh(16) : Ic.layers(16)}
      iconTint={
        reviewing
          ? reviewHeader.running
            ? "var(--chrome-accent)"
            : stageTone(PAGE.EVALUATE)
          : authoring.nextPage
            ? stageTone(authoring.nextPage)
            : "var(--status-ok)"
      }
      title={`Workflow · ${reviewing ? "Review" : "Authoring"}`}
      subtitle={subtitle}
      on={active}
      expandLabel="Expand workflow"
      collapseLabel="Collapse workflow"
      bodyMaxHeight={reviewing ? 430 : 220}
      bodyClassName={hud.workflowBody}
    >
      <div role="tablist" aria-label="Workflow mode" className={styles.tabs}>
        <button
          ref={authoringTab}
          id={`${id}-authoring-tab`}
          type="button"
          role="tab"
          aria-selected={!reviewing}
          aria-controls={`${id}-authoring-panel`}
          className={styles.tab}
          onClick={() => selectMode("authoring")}
          onKeyDown={(event) => handleTabKey(event, "authoring")}
        >
          Authoring
          <span>
            {authoring.complete}/{authoring.steps.length}
          </span>
        </button>
        <button
          ref={reviewTab}
          id={`${id}-review-tab`}
          type="button"
          role="tab"
          aria-selected={reviewing}
          aria-controls={`${id}-review-panel`}
          className={styles.tab}
          onClick={() => selectMode("review")}
          onKeyDown={(event) => handleTabKey(event, "review")}
        >
          Review
          <span>{reviewHeader.complete}/4</span>
        </button>
      </div>

      <div
        id={`${id}-authoring-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-authoring-tab`}
        hidden={reviewing}
        className={styles.panel}
      >
        <AuthoringWorkflowPanel page={page} model={authoring} onNavigate={onNavigate} />
      </div>
      <div
        id={`${id}-review-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-review-tab`}
        hidden={!reviewing}
        className={styles.reviewPanel}
      >
        <ReviewWorkflowPanel experiments={experiments} onHeaderChange={setReviewHeader} />
      </div>
    </HudConsole>
  );
}
