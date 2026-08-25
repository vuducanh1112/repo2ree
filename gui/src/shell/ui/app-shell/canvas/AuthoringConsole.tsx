import {
  type AuthoringStep,
  type AuthoringStepStatus,
  authoringPageForStep,
  authoringStepStatuses,
} from "@core/app-shell/authoringDag";
import type { AppShellPage } from "@core/app-shell/pages";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useAuthoringStepsQuery } from "@shell/data/reeSteps/queries";
import styles from "./authoring/AuthoringConsole.module.css";

interface AuthoringWorkflowPanelProps {
  page: AppShellPage;
  model: AuthoringWorkflowModel;
  onNavigate: (page: AppShellPage) => void;
}

interface AuthoringWorkflowModel {
  steps: readonly AuthoringStep[];
  statuses: Readonly<Record<string, AuthoringStepStatus>>;
  complete: number;
  nextPage: AppShellPage | undefined;
  active: boolean;
  error: boolean;
}

/** API-driven authoring graph and per-REE progress projected onto it. */
export function useAuthoringWorkflowModel(
  ree: ReeEditorViewModel,
  badges: Badges,
): AuthoringWorkflowModel {
  const catalog = useAuthoringStepsQuery();
  const steps = catalog.data ?? [];
  const statuses = authoringStepStatuses(steps, ree, badges);
  const complete = steps.filter((step) => statuses[step.key] === "complete").length;
  const next = steps.find((step) => statuses[step.key] === "ready");
  const nextPage = next ? authoringPageForStep(next.key) : undefined;

  return {
    steps,
    statuses,
    complete,
    nextPage,
    active: complete > 0,
    error: catalog.isError,
  };
}

/** Navigation panel rendered inside the shared workflow HUD. */
export function AuthoringWorkflowPanel({ page, model, onNavigate }: AuthoringWorkflowPanelProps) {
  return (
    <>
      {model.error ? (
        <div role="alert" className={styles.error}>
          Authoring guidance is unavailable. You can still use the workbench terminals.
        </div>
      ) : (
        <AuthoringDag
          steps={model.steps}
          statuses={model.statuses}
          page={page}
          onNavigate={onNavigate}
        />
      )}
    </>
  );
}

function AuthoringDag({
  steps,
  statuses,
  page,
  onNavigate,
}: {
  steps: readonly AuthoringStep[];
  statuses: Readonly<Record<string, AuthoringStepStatus>>;
  page: AppShellPage;
  onNavigate: (page: AppShellPage) => void;
}) {
  const labelByKey = new Map(steps.map((step) => [step.key, step.label]));

  return (
    <nav aria-label="Authoring workflow" className={styles.scroller}>
      <ol className={styles.dag}>
        {steps.map((step) => {
          const target = authoringPageForStep(step.key);
          const status = statuses[step.key] ?? "blocked";
          const requirements = step.requires.map((key) => labelByKey.get(key) ?? key).join(" + ");
          return (
            <li key={step.key} className={styles.item}>
              {step.order > 1 ? <span aria-hidden className={styles.edge} /> : null}
              <button
                type="button"
                className={styles.step}
                data-status={status}
                data-active={target === page || undefined}
                aria-current={target === page ? "step" : undefined}
                aria-label={`Open ${step.label} authoring step, ${status}${requirements ? `, requires ${requirements}` : ""}`}
                disabled={!target}
                onClick={() => {
                  if (target) onNavigate(target);
                }}
              >
                <span className={styles.number}>{String(step.order).padStart(2, "0")}</span>
                <span className={styles.label}>{step.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
