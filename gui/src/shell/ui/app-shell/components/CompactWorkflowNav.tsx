import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useEffect, useState } from "react";
import styles from "./CompactWorkflowNav.module.css";

interface CompactWorkflowNavProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  badges: Badges;
  onNavigate: (page: AppShellPage) => void;
}

export function CompactWorkflowNav({ page, ree, badges, onNavigate }: CompactWorkflowNavProps) {
  const [open, setOpen] = useState(false);
  const current = PROCESS_STEPS.find((step) => step.key === page)?.label ?? "Overview";

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const navigate = (next: AppShellPage) => {
    setOpen(false);
    onNavigate(next);
  };

  return (
    <div className={styles.root}>
      <button
        type="button"
        className={styles.toggle}
        aria-label={`${open ? "Close" : "Open"} workflow navigation, current step: ${current}`}
        aria-expanded={open}
        aria-controls="compact-workflow-navigation"
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden className={styles.toggleGlyph}>
          ☰
        </span>
        <span className={styles.toggleLabel}>{current}</span>
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close workflow navigation"
            className={styles.scrim}
            onClick={() => setOpen(false)}
          />
          <nav id="compact-workflow-navigation" aria-label="REE workflow" className={styles.menu}>
            <button
              type="button"
              className={styles.overview}
              aria-label="Canvas overview"
              aria-current={page === PAGE.CANVAS ? "page" : undefined}
              onClick={() => navigate(PAGE.CANVAS)}
            >
              <span className={styles.stepNumber}>00</span>
              <span>Canvas overview</span>
            </button>
            <ol className={styles.steps}>
              {PROCESS_STEPS.map((step) => {
                const complete = resolveNavCompleted(step, ree, badges);
                return (
                  <li key={step.key}>
                    <button
                      type="button"
                      className={styles.step}
                      aria-label={`${String(step.n)}. ${step.label}, ${complete ? "complete" : "pending"}`}
                      data-complete={complete || undefined}
                      aria-current={page === step.key ? "step" : undefined}
                      onClick={() => navigate(step.key)}
                    >
                      <span className={styles.stepNumber}>{String(step.n).padStart(2, "0")}</span>
                      <span className={styles.stepLabel}>{step.label}</span>
                      <span className={styles.status}>{complete ? "Complete" : "Pending"}</span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>
        </>
      )}
    </div>
  );
}
