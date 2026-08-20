import { APP_ROUTE, type AppLoadRoutePath, LOAD_REE_PARAM } from "@core/app-shell/pages";
import { AXES } from "@core/evaluate/axes";
import type { ReactNode } from "react";
import { Ic } from "../shared/components/Icon";
import { axisTone } from "../theme/appearance";
import { cssVars } from "../theme/styleVars";
import styles from "./LandingView.module.css";

interface LandingViewProps {
  onLoad: (path: AppLoadRoutePath) => void;
  onViewAgents: () => void;
  onViewReeIndex: () => void;
}

function LandingAction({
  icon,
  label,
  primary = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  primary?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={styles.action}
      data-emphasis={primary ? "primary" : undefined}
    >
      <span aria-hidden className={styles.actionIcon}>
        {icon}
      </span>
      {label}
    </button>
  );
}

export function LandingView({ onLoad, onViewAgents, onViewReeIndex }: LandingViewProps) {
  // Both entry points run the same creation flow: pick a lab location (agent),
  // then the workbench step — which is also where an existing REE bundle is
  // loaded, since the load runs on the workbench that step provisions.
  const createRee = () => {
    onLoad(APP_ROUTE.LAB_LOCATION);
  };
  const loadRee = () => {
    onLoad(`${APP_ROUTE.LAB_LOCATION}?${LOAD_REE_PARAM}=1`);
  };

  return (
    <main className={styles.screen}>
      <div className={styles.column}>
        <div className={styles.masthead}>
          <div aria-hidden className={styles.mark}>
            {Ic.layers(22)}
          </div>
          <h1 className={styles.title}>REE Workspace</h1>
          <p className={styles.tagline}>
            Build, inspect, and certify
            <br />
            Reproducible Execution Environments
          </p>
        </div>

        <div className={styles.actions}>
          <div className={styles.sectionLabel}>Choose Action</div>
          <LandingAction icon={Ic.play()} label="Create REE" primary onClick={createRee} />
          <LandingAction icon={Ic.upload(15)} label="Load REE" onClick={loadRee} />
          <LandingAction icon={Ic.cpu(15)} label="View Agents" onClick={onViewAgents} />
          <LandingAction icon={Ic.archive(15)} label="REE Index" onClick={onViewReeIndex} />
        </div>

        <div className={styles.axes}>
          {AXES.map((axis) => (
            <div key={axis.key} className={styles.axis}>
              <div
                aria-hidden
                className={styles.axisDot}
                style={cssVars({ "--axis-tint": axisTone(axis.key) })}
              />
              {axis.label} ({axis.steps.join(" → ")})
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
