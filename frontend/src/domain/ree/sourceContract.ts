import type { Ree } from "../../types";

export function enforceSourceOriginContract(ree: Ree): Ree {
  const hasDownloadedSource = !!ree._sourceAvailable && ree._sourceAcquiredBy === "download";
  const hasUploadedSource = !!ree._sourceAvailable && ree._sourceAcquiredBy === "upload";

  let nextRee = ree;
  if (!hasDownloadedSource && nextRee.origin_url) {
    nextRee = { ...nextRee, origin_url: "" };
  }
  if (hasUploadedSource && !nextRee._sourceIncluded) {
    nextRee = { ...nextRee, _sourceIncluded: true };
  }
  return nextRee;
}
