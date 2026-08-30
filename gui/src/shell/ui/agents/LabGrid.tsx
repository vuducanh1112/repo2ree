import type { Agent } from "@core/agent/Agent";
import type { KeyboardEvent } from "react";
import { cssVars } from "../theme/styleVars";
import { LabCell } from "./LabCell";
import styles from "./LabGrid.module.css";

interface LabGridProps {
  /** The agents on the current page, already sliced. */
  agents: Agent[];
  columns: number;
  nowMs: number;
  selectedId: string | null;
  onSelect: (agentId: string) => void;
}

/**
 * The page of bays. Owns arrow-key movement across the grid; selection follows
 * focus, which is the expected behaviour for a single-choice group and saves
 * the user a second keystroke on every bay they look at.
 */
export function LabGrid({ agents, columns, nowMs, selectedId, onSelect }: LabGridProps) {
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
      {agents.map((agent) => (
        <LabCell
          key={agent.id}
          agent={agent}
          nowMs={nowMs}
          selected={agent.id === selectedId}
          onSelect={() => onSelect(agent.id)}
        />
      ))}
    </div>
  );
}
