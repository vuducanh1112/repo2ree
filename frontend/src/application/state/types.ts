export type Updater<T> = T | ((previous: T) => T);

export function resolveUpdater<T>(previous: T, updater: Updater<T>): T {
  return typeof updater === "function" ? (updater as (value: T) => T)(previous) : updater;
}
