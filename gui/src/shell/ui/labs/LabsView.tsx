import type { Lab } from "@core/lab/Lab";
import { useLabs } from "@shell/data/labs/labs";
import { Ic } from "../shared/components/Icon";
import styles from "./LabsView.module.css";
import { labLoadErrorMessage } from "./labPresentation";
import { NoLabsState } from "./NoLabsState";

interface LabsViewProps {
  onBack: () => void;
}

export function LabsView({ onBack }: LabsViewProps) {
  const { data: labs, isLoading, isError, error, refetch, isFetching } = useLabs();

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
            labs.map((lab) => <LabRow key={lab.id} lab={lab} />)
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
      <div className={styles.headCell}>Location</div>
      <div className={styles.headCell}>Location ID</div>
      <div className={styles.headCell}>Lifecycle</div>
      <div className={styles.headCell}>Images</div>
      <div className={styles.headCell}>Availability</div>
    </div>
  );
}

function LabRow({ lab }: { lab: Lab }) {
  return (
    <div className={styles.row}>
      <div className={styles.host}>
        <span className={styles.hostIcon} title="Connected">
          {Ic.cpu(15)}
        </span>
        <span className={styles.hostName}>{lab.label}</span>
      </div>
      <div className={styles.cell} data-flavor="code">
        {lab.id}
      </div>
      <div className={styles.cell}>
        {lab.lifecycleMode === "provider_managed" ? "on demand" : "pre-provisioned"}
      </div>
      <div className={styles.cell}>
        {lab.lifecycleMode === "provider_managed" ? lab.images.length : "—"}
      </div>
      <div className={styles.uptime}>
        <span aria-hidden className={styles.uptimeDot} />
        <span className={styles.cell}>{lab.available ? "available" : "busy"}</span>
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
