import type { Lab } from "./Lab";

const ROWS_PER_PAGE = 2;

function columnsFor(total: number): number {
  if (total <= 2) return 2;
  if (total <= 6) return 3;
  return 4;
}

function matches(lab: Lab, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return lab.label.toLowerCase().includes(needle) || lab.id.toLowerCase().includes(needle);
}

export interface LabPage {
  matches: Lab[];
  visible: Lab[];
  columns: number;
  page: number;
  pageCount: number;
}

export function selectLabPage(
  labs: readonly Lab[],
  { query, page }: { query: string; page: number },
): LabPage {
  const found = labs.filter((lab) => matches(lab, query));
  const columns = columnsFor(found.length);
  const size = columns * ROWS_PER_PAGE;
  const pageCount = Math.max(1, Math.ceil(found.length / size));
  const current = Math.min(Math.max(0, page), pageCount - 1);
  return {
    matches: found,
    visible: found.slice(current * size, current * size + size),
    columns,
    page: current,
    pageCount,
  };
}
