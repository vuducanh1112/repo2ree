import type { CSSProperties } from "react";

type CssVarName = `--${string}`;

export type CssVarValues = Readonly<Partial<Record<CssVarName, string | number>>>;

export function cssVars(values: CssVarValues): CSSProperties {
  const declared: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(values)) {
    if (value !== undefined) declared[name] = value;
  }
  return declared as CSSProperties;
}

export function cx(...names: ReadonlyArray<string | false | null | undefined>): string {
  return names.filter(Boolean).join(" ");
}
