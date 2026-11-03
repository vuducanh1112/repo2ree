import type { Lab } from "@core/lab/Lab";
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
  const onHost = lab.backend === "host";
  // A container lab with no images has nothing a new REE could declare, so it takes none.
  const available = lab.available && (onHost || lab.images.length > 0);
  const what =
    lab.description ||
    (lab.status === "offline"
      ? "Its workbench is away; its REEs wait for it."
      : onHost
        ? "Runs each REE's scripts on its own machine."
        : "Runs each REE's scripts in a container from its image.");
  const meta = onHost
    ? "its own machine"
    : `${lab.images.length} image${lab.images.length === 1 ? "" : "s"}`;

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
