/**
 * Format byte count as human-readable string (B, KB, MB)
 */
export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Detect a rough file type from the path for syntax-hinting.
 */
export function fileType(path: string): string {
  if (!path) return "text";
  const ext = path.split(".").pop().toLowerCase();
  if (["sh", "bash"].includes(ext)) return "shell";
  if (
    ["dockerfile", "containerfile"].includes(path.split("/").pop().toLowerCase()) ||
    ext === "dockerfile"
  )
    return "dockerfile";
  if (["json", "jsonc"].includes(ext)) return "json";
  if (["py"].includes(ext)) return "python";
  if (["nix"].includes(ext)) return "nix";
  if (["md"].includes(ext)) return "markdown";
  if (["lock", "toml", "yaml", "yml"].includes(ext)) return "config";
  return "text";
}
