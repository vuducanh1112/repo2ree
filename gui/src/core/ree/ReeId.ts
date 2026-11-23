export type ReeId = string & { readonly __brand: "ReeId" };

export function asReeId(value: string): ReeId {
  return value as ReeId;
}

export const DEFAULT_REE_ID: ReeId = asReeId("active");
