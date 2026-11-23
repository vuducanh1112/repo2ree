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
