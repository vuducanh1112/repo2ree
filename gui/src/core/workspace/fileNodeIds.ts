/**
 * Node ids for the file console's two inventories.
 *
 * The console browses the workspace and the REE as sections of one tree and
 * keys its open tabs by node id, so ids have to be unique across the pair: the
 * workspace is materialized from `upstream/` plus `overlay/`, so the same path
 * genuinely occurs in both. They also have to be derived from the path rather
 * than from position — the console prunes tabs whose id it can no longer find,
 * so an id that shifted when a neighbour arrived would close open tabs.
 *
 * The four builders live together because that uniqueness is a property of the
 * set, not of any one of them.
 */

export function workspaceFileId(path: string): string {
  return `ws:${path}`;
}

export function workspaceDirId(path: string): string {
  return `ws-dir:${path}`;
}

export function reeFileId(path: string): string {
  return `ree:${path}`;
}

export function reeDirId(path: string): string {
  return `ree-dir:${path}`;
}
