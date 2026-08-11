import type { CSSProperties } from "react";

/** The two helpers a CSS-Module component is allowed to reach for.
 *
 * `styleVars` is deliberately tiny. It is not a place for style objects: the
 * only values that may reach a `style` prop are runtime-calculated CSS custom
 * properties, and `cssVars` is the one thing that produces them. Everything a
 * component knows at build time belongs in its `.module.css`.
 */

/** A CSS custom property name — `--window-x`, not `windowX`. */
type CssVarName = `--${string}`;

/** Calculated custom properties. `undefined` drops the property, which lets a
 * caller write one object for both the "measured" and "not yet measured"
 * renders rather than branching on the whole `style` prop.
 *
 * Neither name is exported: call sites pass an object literal, and the literal
 * key type is what makes `--windowX` a compile error. */
type CssVarValues = Readonly<Partial<Record<CssVarName, string | number>>>;

/** Pack calculated custom properties into a `style` prop.
 *
 * ```tsx
 * <div className={styles.window} style={cssVars({ "--window-x": `${x}px` })} />
 * ```
 *
 * React types `style` as `CSSProperties`, which does not admit custom
 * properties, so the assertion here is the single place the cast lives instead
 * of once per call site.
 */
export function cssVars(values: CssVarValues): CSSProperties {
  const declared: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(values)) {
    if (value !== undefined) declared[name] = value;
  }
  return declared as CSSProperties;
}

/** Join class names, dropping the falsy ones.
 *
 * ```tsx
 * <button className={cx(styles.button, running && styles.busy)} />
 * ```
 */
export function cx(...names: ReadonlyArray<string | false | null | undefined>): string {
  return names.filter(Boolean).join(" ");
}
