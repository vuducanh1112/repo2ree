import type { Lab } from "@core/lab/Lab";
import type { KeyboardEvent } from "react";
import { cssVars } from "../theme/styleVars";
import { LabCell } from "./LabCell";
import styles from "./LabGrid.module.css";

interface LabGridProps {
  labs: Lab[];
  columns: number;
  selectedId: string | null;
  onSelect: (labId: string) => void;
}

export function LabGrid({ labs, columns, selectedId, onSelect }: LabGridProps) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const step: Record<string, number> = {
      ArrowRight: 1,
      ArrowLeft: -1,
      ArrowDown: columns,
      ArrowUp: -columns,
    };
    const delta = step[event.key];
    if (delta === undefined) return;

    const cells = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>("button[data-lab]"),
    );
    const here = cells.indexOf(document.activeElement as HTMLButtonElement);
    if (here === -1) return;

    event.preventDefault();
    const next = cells[Math.min(cells.length - 1, Math.max(0, here + delta))];
    if (!next?.dataset.lab) return;
    next.focus();
    onSelect(next.dataset.lab);
  }

  return (
    // biome-ignore lint/a11y/useSemanticElements: a grouped set of buttons, not a listbox
    <div
      role="group"
      aria-label="Connected labs"
      onKeyDown={onKeyDown}
      className={styles.grid}
      style={cssVars({ "--lab-columns": String(columns) })}
    >
      {labs.map((lab) => (
        <LabCell
          key={lab.id}
          lab={lab}
          selected={lab.id === selectedId}
          onSelect={() => onSelect(lab.id)}
        />
      ))}
    </div>
  );
}
