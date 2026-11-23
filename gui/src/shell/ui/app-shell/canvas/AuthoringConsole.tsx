import { authoringPageForStep } from "@core/app-shell/authoringDag";
import type { AppShellPage } from "@core/app-shell/pages";
import type {
  AuthoringStep,
  AuthoringStepKey,
  AuthoringStepStatus,
} from "@core/ree/AuthoringProgress";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import styles from "./authoring/AuthoringConsole.module.css";

interface AuthoringWorkflowPanelProps {
  page: AppShellPage;
  model: AuthoringWorkflowModel;
  onNavigate: (page: AppShellPage) => void;
}

export interface AuthoringWorkflowModel {
  steps: readonly AuthoringStep[];
  statuses: Readonly<Partial<Record<AuthoringStepKey, AuthoringStepStatus>>>;
  complete: number;
  nextKey: AuthoringStepKey | undefined;
  nextPage: AppShellPage | undefined;
  active: boolean;
}

export function authoringWorkflowModel(ree: ReeEditorViewModel): AuthoringWorkflowModel {
  const { steps, next } = ree.steps;
  const statuses = Object.fromEntries(steps.map((step) => [step.key, step.status]));
  const complete = steps.filter((step) => step.status === "complete").length;

  return {
    steps,
    statuses,
    complete,
    nextKey: next,
    nextPage: next ? authoringPageForStep(next) : undefined,
    active: complete > 0,
  };
}

export function AuthoringWorkflowPanel({ page, model, onNavigate }: AuthoringWorkflowPanelProps) {
  return (
    <AuthoringDag
      steps={model.steps}
      statuses={model.statuses}
      nextKey={model.nextKey}
      page={page}
      onNavigate={onNavigate}
    />
  );
}

function AuthoringDag({
  steps,
  statuses,
  nextKey,
  page,
  onNavigate,
}: {
  steps: readonly AuthoringStep[];
  statuses: Readonly<Partial<Record<AuthoringStepKey, AuthoringStepStatus>>>;
  nextKey: AuthoringStepKey | undefined;
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
          const next = step.key === nextKey;
          return (
            <li key={step.key} className={styles.item}>
              {step.order > 1 ? <span aria-hidden className={styles.edge} /> : null}
              <button
                type="button"
                className={styles.step}
                data-status={status}
                data-next={next || undefined}
                data-active={target === page || undefined}
                aria-current={target === page ? "step" : undefined}
                aria-label={`Open ${step.label} authoring step, ${status}${next ? ", next up" : ""}${requirements ? `, requires ${requirements}` : ""}`}
                onClick={() => onNavigate(target)}
              >
                <span className={styles.number}>{String(step.order).padStart(2, "0")}</span>
                {next ? <span className={styles.nextTag}>next</span> : null}
                <span className={styles.label}>{step.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
