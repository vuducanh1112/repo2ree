import { describeMachine, type Lab } from "@core/lab/Lab";
import { Ic } from "../shared/components/Icon";
import styles from "./LabCell.module.css";

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
  const name = lab.label;
  const available = lab.available;
  const what =
    lab.description ||
    (lab.status === "offline"
      ? "Its workbench is away; its REEs wait for it."
      : lab.machine?.engine === "none"
        ? "Runs each REE's scripts on its own machine; it has no engine for an image."
        : "Runs each REE's scripts in the image it declares, or on its own machine.");
  const meta = describeMachine(lab.machine);

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
        <span className={styles.what}>{what}</span>
        <span className={styles.meta}>{meta}</span>
      </span>
      <span aria-hidden className={styles.foot}>
        {selected
          ? "selected"
          : available
            ? "select"
            : lab.status === "offline"
              ? "offline"
              : "busy"}
      </span>
    </button>
  );
}
