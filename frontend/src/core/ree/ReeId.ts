export type ReeId = string & { readonly __brand: "ReeId" };

export function asReeId(value: string): ReeId {
  return value as ReeId;
}

// Sentinel id meaning "no REE provisioned yet" — used when the URL carries no
// reeId. It never refers to a real REE; code treats reeId === DEFAULT_REE_ID as
// the unprovisioned state and as the trigger to lazily create one.
export const DEFAULT_REE_ID: ReeId = asReeId("active");
