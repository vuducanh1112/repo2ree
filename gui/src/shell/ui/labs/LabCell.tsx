import type { Lab } from "@core/lab/Lab";
import { Ic } from "../shared/components/Icon";
import styles from "./LabCell.module.css";
import { dockerModeCopy } from "./labPresentation";

interface LabCellProps {
  lab: Lab;
  selected: boolean;
  onSelect: () => void;
}

/**
 * One lab, as a bay on the deck. Everything inside is `aria-hidden` and the
 * control is named by `aria-label` instead: the state is shown by a lamp that
 * carries no text, so the accessible name has to say it.
 */
export function LabCell({ lab, selected, onSelect }: LabCellProps) {
  const profile = lab.profiles[0];
  const mode = dockerModeCopy(profile?.substrate ?? "");
  const name = lab.label;
  const available = lab.available && lab.profiles.length > 0;

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={!available}
      aria-pressed={selected}
      aria-label={`${name} — ${available ? "available" : "unavailable"}`}
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
        <span
          className={styles.meta}
        >{`${mode.readout} · ${lab.profiles.length} profile${lab.profiles.length === 1 ? "" : "s"}`}</span>
      </span>
      <span aria-hidden className={styles.foot}>
        {selected ? "selected" : available ? "select" : "busy"}
      </span>
    </button>
  );
}
