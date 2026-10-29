const BYTES_PER_GIB = 1024 ** 3;
const MBPS_PER_GBPS = 1000;

export function gibFromBytes(bytes: number): number {
  return bytes / BYTES_PER_GIB;
}

export function bytesFromGib(gib: unknown): number {
  return Math.max(0, Math.round(Number(gib) * BYTES_PER_GIB) || 0);
}

export function gbpsFromMbps(mbps: number): number {
  return mbps / MBPS_PER_GBPS;
}

export function mbpsFromGbps(gbps: unknown): number {
  return Math.max(0, Math.round(Number(gbps) * MBPS_PER_GBPS) || 0);
}
