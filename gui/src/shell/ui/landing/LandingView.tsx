import { APP_ROUTE, type AppLoadRoutePath, LOAD_REE_PARAM } from "@core/app-shell/pages";
import { useAgents } from "@shell/data/agents/agents";
import type { ReactNode } from "react";
import { Ic } from "../shared/components/Icon";
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

function AgentReadiness({ onViewAgents }: { onViewAgents: () => void }) {
  const { data: agents, isLoading, isError } = useAgents();

  if (isLoading) {
    return (
      <div className={styles.readiness} role="status">
        <span aria-hidden className={styles.readinessDot} data-state="checking" />
        Checking for a connected workbench agent…
      </div>
    );
  }

  if (!isError && agents?.length) {
    return (
      <div className={styles.readiness} role="status">
        <span aria-hidden className={styles.readinessDot} data-state="ready" />A connected agent is
        ready to provision your workbench.
      </div>
    );
  }

  return (
    <div className={styles.readiness} role="status">
      <span aria-hidden className={styles.readinessDot} data-state="missing" />
      <span>{isError ? "Agent status is unavailable." : "No workbench agent is connected."}</span>
      <button type="button" className={styles.readinessLink} onClick={onViewAgents}>
        View agents
      </button>
    </div>
  );
}

function GithubDestination() {
  const githubUrl = import.meta.env.VITE_GITHUB_URL;
  const content = (
    <>
      <span aria-hidden>{Ic.github(16)}</span>
      <span>GitHub</span>
    </>
  );

  if (githubUrl) {
    return (
      <a className={styles.utility} href={githubUrl} target="_blank" rel="noreferrer">
        {content}
      </a>
    );
  }

  return (
    <span className={styles.utility} aria-disabled="true" title="GitHub link not configured">
      {content}
    </span>
  );
}

export function LandingView({ onLoad, onViewAgents, onViewReeIndex }: LandingViewProps) {
  const createRee = () => onLoad(APP_ROUTE.LAB_LOCATION);
  const loadRee = () => onLoad(`${APP_ROUTE.LAB_LOCATION}?${LOAD_REE_PARAM}=1`);

  return (
    <main className={styles.screen}>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <span aria-hidden className={styles.brandMark}>
            {Ic.layers(19)}
          </span>
          <span className={styles.brandName}>repo2ree</span>
        </div>

        <nav className={styles.utilities} aria-label="Workspace utilities">
          <button type="button" className={styles.utility} onClick={onViewReeIndex}>
            <span aria-hidden>{Ic.archive(16)}</span>
            <span>REE index</span>
          </button>
          <GithubDestination />
        </nav>
      </header>

      <div className={styles.content}>
        <section className={styles.hero} aria-labelledby="landing-title">
          <div className={styles.intro}>
            <div className={styles.eyebrow}>Reproducible execution environments</div>
            <h1 id="landing-title" className={styles.title}>
              Turn research code into <em>evidence.</em>
            </h1>
            <p className={styles.lede}>
              Package source, runtime, and experiments into one verifiable artifact—ready for a
              reviewer to run again, inspect, and cite.
            </p>

            <div className={styles.actions}>
              <LandingAction
                icon={Ic.plus(17)}
                label="Create a new REE"
                primary
                onClick={createRee}
              />
              <LandingAction icon={Ic.upload(17)} label="Load existing REE" onClick={loadRee} />
            </div>

            <AgentReadiness onViewAgents={onViewAgents} />
          </div>

          <figure className={styles.preview}>
            <div className={styles.previewWindow}>
              <div className={styles.previewBar}>
                <span aria-hidden className={styles.windowLights}>
                  <i />
                  <i />
                  <i />
                </span>
                <span className={styles.windowTitle}>climate-model-lab / workbench</span>
              </div>
              <div className={styles.screenshotFrame}>
                <img
                  className={styles.screenshot}
                  src="/landing-workbench.jpg"
                  alt="The repo2ree workbench canvas, with a central specimen pod connected to source, metadata, runtime, experiment, review, and archive stations."
                />
                <div className={styles.previewNote}>
                  <span>The actual workbench</span>
                  <strong>Every reproducibility decision stays visible around the REE.</strong>
                </div>
              </div>
            </div>
            <figcaption className={styles.previewCaption}>
              <span>
                <strong>A visual assembly bench—not another form wizard.</strong>
                Configure each layer, run it in isolation, and collect the evidence needed to verify
                it later.
              </span>
              <b>Interactive canvas</b>
            </figcaption>
          </figure>
        </section>

        <section className={styles.nextSteps} aria-labelledby="next-steps-title">
          <h2 id="next-steps-title">What happens after “Create”</h2>
          <div className={styles.stepGrid}>
            <article className={styles.step}>
              <span className={styles.stepNumber}>01</span>
              <div>
                <h3>Choose a lab</h3>
                <p>Select a connected agent to host an isolated workbench.</p>
              </div>
            </article>
            <article className={styles.step}>
              <span className={styles.stepNumber}>02</span>
              <div>
                <h3>Assemble the environment</h3>
                <p>Bring in source, declare hardware and runtime, then define experiments.</p>
              </div>
            </article>
            <article className={styles.step}>
              <span className={styles.stepNumber}>03</span>
              <div>
                <h3>Run, review, and seal</h3>
                <p>Capture execution receipts and download the resulting REE bundle.</p>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  );
}
