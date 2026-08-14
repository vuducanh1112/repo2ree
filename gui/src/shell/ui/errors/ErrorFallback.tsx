import { type ReactNode, useEffect, useRef } from "react";
import { Button } from "../shared/components/Button";
import { Ic } from "../shared/components/Icon";
import styles from "./ErrorFallback.module.css";

interface ErrorFallbackFrameProps {
  title: string;
  message: string;
  reassurance: string;
  children: ReactNode;
}

function ErrorFallbackFrame({ title, message, reassurance, children }: ErrorFallbackFrameProps) {
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  return (
    <main className={styles.screen}>
      <section className={styles.card} role="alert" aria-labelledby="error-fallback-title">
        <span aria-hidden className={styles.icon}>
          {Ic.info(28)}
        </span>
        <h1 id="error-fallback-title" ref={titleRef} tabIndex={-1} className={styles.title}>
          {title}
        </h1>
        <p className={styles.message}>{message}</p>
        <p className={styles.reassurance}>{reassurance}</p>
        <div className={styles.actions}>{children}</div>
      </section>
    </main>
  );
}

interface ApplicationErrorFallbackProps {
  onRetry: () => void;
  onReturnHome: () => void;
  onReload: () => void;
}

export function ApplicationErrorFallback({
  onRetry,
  onReturnHome,
  onReload,
}: ApplicationErrorFallbackProps) {
  return (
    <ErrorFallbackFrame
      title="REE Workspace encountered a problem"
      message="The application could not display this screen. You can try again or restart from the home screen."
      reassurance="No workbench or REE was intentionally removed."
    >
      <Button variant="primary" onClick={onRetry} icon={Ic.refresh(14)}>
        Try again
      </Button>
      <Button onClick={onReturnHome} icon={Ic.arrowLeft(14)}>
        Return home
      </Button>
      <Button onClick={onReload}>Reload application</Button>
    </ErrorFallbackFrame>
  );
}

interface WorkspaceErrorFallbackProps {
  onRetry: () => void;
  onBack: () => void;
}

export function WorkspaceErrorFallback({ onRetry, onBack }: WorkspaceErrorFallbackProps) {
  return (
    <ErrorFallbackFrame
      title="This REE workspace could not be displayed"
      message="The editor hit an unexpected problem while rendering this workspace. Try opening it again or return home."
      reassurance="The remote workbench may still be running, and no REE data was intentionally removed."
    >
      <Button variant="primary" onClick={onRetry} icon={Ic.refresh(14)}>
        Try workspace again
      </Button>
      <Button onClick={onBack} icon={Ic.arrowLeft(14)}>
        Return home
      </Button>
    </ErrorFallbackFrame>
  );
}
