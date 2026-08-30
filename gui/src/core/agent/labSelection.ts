import type { Agent } from "./Agent";

// The grid is two rows tall, so a page holds twice the column count.
const ROWS_PER_PAGE = 2;

// Fewer columns for a small fleet, so two labs don't stretch a cell across the
// whole deck. Pure.
function columnsFor(total: number): number {
  if (total <= 2) return 2;
  if (total <= 6) return 3;
  return 4;
}

// Hostname or agent id, case-insensitively, on a trimmed query. Pure.
function matches(agent: Agent, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return agent.hostname.toLowerCase().includes(needle) || agent.id.toLowerCase().includes(needle);
}

export interface LabPage {
  /** Every agent matching the query, in the order given. */
  matches: Agent[];
  /** The slice the current page renders. */
  visible: Agent[];
  /** Grid columns for this result count. */
  columns: number;
  /** The requested page, clamped into range — a filter can shrink the list
   * under the page the user is standing on. */
  page: number;
  /** Never zero: an empty result set is still one (empty) page. */
  pageCount: number;
}

/**
 * Everything the lab grid needs to draw one page, derived from the fleet and
 * the filter. Pure — the view holds `query` and `page` and nothing else, so
 * paging and filtering are testable without a DOM.
 */
export function selectLabPage(
  agents: readonly Agent[],
  { query, page }: { query: string; page: number },
): LabPage {
  const found = agents.filter((agent) => matches(agent, query));
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
