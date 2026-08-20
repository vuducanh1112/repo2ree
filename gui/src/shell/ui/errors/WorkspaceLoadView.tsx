import { Button } from "../shared/components/Button";
import { Ic } from "../shared/components/Icon";
import styles from "./WorkspaceLoadView.module.css";

export function WorkspaceLoadingView({ onBack }: { onBack: () => void }) {
  return (
    <main className={styles.screen}>
      <section
        className={styles.card}
        data-tone="loading"
        role="status"
        aria-live="polite"
        aria-labelledby="workspace-loading-title"
      >
        <span aria-hidden className={styles.icon}>
          {Ic.refresh(28)}
        </span>
        <h1 id="workspace-loading-title" className={styles.title}>
          Loading workspace
        </h1>
        <p className={styles.message}>Fetching the current REE definition and files…</p>
        <div className={styles.actions}>
          <Button onClick={onBack} icon={Ic.arrowLeft(14)}>
            Return home
          </Button>
        </div>
      </section>
    </main>
  );
}

interface WorkspaceLoadErrorViewProps {
  error: Error;
  onRetry: () => void;
  onBack: () => void;
}

export function WorkspaceLoadErrorView({ error, onRetry, onBack }: WorkspaceLoadErrorViewProps) {
  return (
    <main className={styles.screen}>
      <section
        className={styles.card}
        data-tone="error"
        role="alert"
        aria-labelledby="workspace-load-error-title"
      >
        <span aria-hidden className={styles.icon}>
          {Ic.info(28)}
        </span>
        <h1 id="workspace-load-error-title" className={styles.title}>
          This workspace could not be loaded
        </h1>
        <p className={styles.message}>{error.message}</p>
        <p className={styles.reassurance}>No local changes were sent to the workbench.</p>
        <div className={styles.actions}>
          <Button variant="primary" onClick={onRetry} icon={Ic.refresh(14)}>
            Try again
          </Button>
          <Button onClick={onBack} icon={Ic.arrowLeft(14)}>
            Return home
          </Button>
        </div>
      </section>
    </main>
  );
}
