import type { Lab } from "@core/lab/Lab";
import { connectedDurationMs, formatDuration } from "@core/lab/Lab";
import { Ic } from "../shared/components/Icon";
import styles from "./LabCell.module.css";
import { dockerModeCopy } from "./labPresentation";

interface LabCellProps {
  lab: Lab;
  /** Shared wall clock, so every bay's uptime ticks together. */
  nowMs: number;
  selected: boolean;
  onSelect: () => void;
}

/**
 * One lab, as a bay on the deck. Everything inside is `aria-hidden` and the
 * control is named by `aria-label` instead: the state is shown by a lamp that
 * carries no text, so the accessible name has to say it.
 */
export function LabCell({ lab, nowMs, selected, onSelect }: LabCellProps) {
  const mode = dockerModeCopy(lab.dockerMode);
  const uptime = formatDuration(connectedDurationMs(lab, nowMs));
  const name = lab.hostname || lab.id;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${name} — connected`}
      data-lab={lab.id}
      data-selected={selected || undefined}
      className={styles.cell}
    >
      <span aria-hidden className={styles.head}>
        <span className={styles.glyph}>{Ic.cpu(13)}</span>
        <span className={styles.name}>{name}</span>
        <span className={styles.lamp} />
      </span>
      <span aria-hidden className={styles.body}>
        <span className={styles.what}>{mode.line}</span>
        <span className={styles.meta}>{`${mode.readout} · up ${uptime}`}</span>
      </span>
      <span aria-hidden className={styles.foot}>
        {selected ? "selected" : "select"}
      </span>
    </button>
  );
}
