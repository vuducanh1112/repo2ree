import type { LogEntry } from "@core/ree/ReeTypes";
import { useEffect, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { Surface } from "../../shared/components/Surface";
import styles from "./CollapsibleLogCard.module.css";
import { LogPanel } from "./logPanel";

interface CollapsibleLogCardProps {
  log: LogEntry | null;
  running: boolean;
  title: string;
  maxHeight?: number;
}

export function CollapsibleLogCard({ log, running, title, maxHeight }: CollapsibleLogCardProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (running) setOpen(true);
  }, [running]);

  const show = running || open;
  const hint = running ? "Streaming" : log ? "Latest run" : "No runs yet";

  return (
    <Surface>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={styles.toggle}
        aria-expanded={show}
      >
        <span className={styles.heading} data-running={running || undefined}>
          {running && (
            <span aria-hidden className={styles.spinner}>
              {Ic.loader(14)}
            </span>
          )}
          {title}
          <span className={styles.hint}>{hint}</span>
        </span>
        <span aria-hidden className={styles.chevron}>
          {show ? Ic.chevD(14) : Ic.chevR(14)}
        </span>
      </button>
      {show && (
        <div className={styles.body} data-bounded={maxHeight ? true : undefined}>
          {maxHeight ? (
            <Surface
              variant="sunken"
              spacing="flush"
              vars={{ "--log-max-height": `${maxHeight}px` }}
            >
              <LogPanel log={log} running={running} />
            </Surface>
          ) : (
            <LogPanel log={log} running={running} />
          )}
        </div>
      )}
    </Surface>
  );
}
