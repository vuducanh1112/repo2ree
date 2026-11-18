/** A name the backend sent that the generated vocabulary does not know: this build reads an older contract. */
export class UnknownWireNames extends Error {
  constructor(
    readonly where: string,
    readonly names: readonly string[],
  ) {
    super(`${where}: names the contract does not know: ${names.join(", ")}`);
    this.name = "UnknownWireNames";
  }
}

export function isOneOf<T extends string>(known: readonly T[], value: unknown): value is T {
  return typeof value === "string" && (known as readonly string[]).includes(value);
}

/** Refuse any of `names` outside `known`, so a renamed key fails here rather than reading as missing. */
export function requireKnownNames<T extends string>(
  where: string,
  known: readonly T[],
  names: Iterable<unknown>,
): T[] {
  const all = [...names];
  const unknown = all.filter((name) => !isOneOf(known, name)).map(String);
  if (unknown.length) throw new UnknownWireNames(where, unknown);
  return all as T[];
}
