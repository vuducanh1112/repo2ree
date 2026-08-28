import { useEffect, useState } from "react";

/**
 * A value that settles only after it has stopped changing for `delayMs`.
 *
 * React Query has no debounce of its own: the idiom is to debounce the input
 * and key the query on the settled value, which is what keeps a per-keystroke
 * check from becoming a request per keystroke.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
