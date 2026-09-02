import type { Lab } from "@core/lab/Lab";
import { connectedDurationMs, formatDuration } from "@core/lab/Lab";
import { useLabs } from "@shell/data/labs/labs";
import { Ic } from "../shared/components/Icon";
import styles from "./LabsView.module.css";
import { labLoadErrorMessage } from "./labPresentation";
import { NoLabsState } from "./NoLabsState";
import { useLabUptimeClock } from "./useLabUptimeClock";

interface LabsViewProps {
  onBack: () => void;
}

export function LabsView({ onBack }: LabsViewProps) {
  const { data: labs, isLoading, isError, error, refetch, isFetching } = useLabs();

  const nowMs = useLabUptimeClock(Boolean(labs?.length));

  return (
    <div className={styles.screen}>
      <div className={styles.column}>
        <Header onBack={onBack} onRefresh={() => void refetch()} isFetching={isFetching} />

        <div className={styles.table}>
          <HeaderRow />
          {isLoading ? (
            <StatusRow text="Loading labs…" />
          ) : isError ? (
            <StatusRow text={labLoadErrorMessage(error)} tone="error" />
          ) : !labs || labs.length === 0 ? (
            <NoLabsState description="Start one pointing at this control plane:" />
          ) : (
            labs.map((lab) => <LabRow key={lab.id} lab={lab} nowMs={nowMs} />)
          )}
        </div>
      </div>
    </div>
  );
}

function Header({
  onBack,
  onRefresh,
  isFetching,
}: {
  onBack: () => void;
  onRefresh: () => void;
  isFetching: boolean;
}) {
  return (
    <div className={styles.header}>
      <button type="button" onClick={onBack} className={styles.chromeButton}>
        {Ic.arrowLeft(15)} Back
      </button>
      <div className={styles.headings}>
        <h1 className={styles.title}>Lab Locations</h1>
        <p className={styles.subtitle}>
          Workbench services currently dialed into this control plane
        </p>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        title="Refresh"
        className={styles.chromeButton}
        data-busy={isFetching || undefined}
      >
        {Ic.refresh(15)} Refresh
      </button>
    </div>
  );
}

function HeaderRow() {
  return (
    <div className={styles.row} data-kind="head">
      <div className={styles.headCell}>Host</div>
      <div className={styles.headCell}>Lab ID</div>
      <div className={styles.headCell}>Runtime</div>
      <div className={styles.headCell}>Version</div>
      <div className={styles.headCell}>Connected</div>
    </div>
  );
}

function LabRow({ lab, nowMs }: { lab: Lab; nowMs: number }) {
  const uptime = formatDuration(connectedDurationMs(lab, nowMs));
  return (
    <div className={styles.row}>
      <div className={styles.host}>
        <span className={styles.hostIcon} title="Connected">
          {Ic.cpu(15)}
        </span>
        <span className={styles.hostName}>{lab.hostname || "—"}</span>
      </div>
      <div className={styles.cell} data-flavor="code">
        {lab.id}
      </div>
      <div className={styles.cell}>{lab.dockerMode || "—"}</div>
      <div className={styles.cell} data-flavor="code">
        {lab.version || "—"}
      </div>
      <div className={styles.uptime}>
        <span aria-hidden className={styles.uptimeDot} />
        <span className={styles.cell}>{uptime}</span>
      </div>
    </div>
  );
}

function StatusRow({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div className={styles.statusRow} data-tone={tone} role={tone === "error" ? "alert" : "status"}>
      {text}
    </div>
  );
}
