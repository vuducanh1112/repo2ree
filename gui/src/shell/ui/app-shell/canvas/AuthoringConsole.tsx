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
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";
import styles from "./authoring/AuthoringConsole.module.css";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";

interface AuthoringConsoleProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  badges: Badges;
  onNavigate: (page: AppShellPage) => void;
}

/** API-driven authoring graph and the primary guided path through the workbench. */
export function AuthoringConsole({ page, ree, badges, onNavigate }: AuthoringConsoleProps) {
  const [open, setOpen] = useState(false);
  const catalog = useAuthoringStepsQuery();
  const steps = catalog.data ?? [];
  const statuses = authoringStepStatuses(steps, ree, badges);
  const complete = steps.filter((step) => statuses[step.key] === "complete").length;
  const next = steps.find((step) => statuses[step.key] === "ready");
  const nextPage = next ? authoringPageForStep(next.key) : undefined;

  const subtitle = catalog.isPending
    ? "loading authoring graph…"
    : catalog.isError
      ? "authoring graph unavailable"
      : `${complete}/${steps.length} complete${next ? ` · next ${next.label}` : ""}`;

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={1400}
      widthCollapsed={320}
      className={hud.authoringPlacement}
      icon={Ic.layers(16)}
      iconTint={nextPage ? stageTone(nextPage) : "var(--status-ok)"}
      title="Authoring"
      subtitle={subtitle}
      on={complete > 0}
      expandLabel="Expand authoring navigation"
      collapseLabel="Collapse authoring navigation"
      bodyMaxHeight={174}
      bodyClassName={hud.authoringBody}
    >
      {catalog.isError ? (
        <div role="alert" className={styles.error}>
          Authoring guidance is unavailable. You can still use the workbench terminals.
        </div>
      ) : (
        <AuthoringDag steps={steps} statuses={statuses} page={page} onNavigate={onNavigate} />
      )}
    </HudConsole>
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
                <span className={styles.requires} title={requirements || "No prerequisites"}>
                  {requirements ? `after ${step.requires.join(" + ")}` : "independent"}
                </span>
                <span className={styles.status}>{status}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
