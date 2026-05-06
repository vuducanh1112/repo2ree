export type ReeId = string & { readonly __brand: "ReeId" };

export function asReeId(value: string): ReeId {
  return value as ReeId;
}

// The default REE id used when the URL does not specify one. Each REE has
// exactly one workspace; this id refers to the REE.
export const DEFAULT_REE_ID: ReeId = asReeId("active");
