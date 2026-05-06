export type ReeId = string & { readonly __brand: "ReeId" };

export function asReeId(value: string): ReeId {
  return value as ReeId;
}
