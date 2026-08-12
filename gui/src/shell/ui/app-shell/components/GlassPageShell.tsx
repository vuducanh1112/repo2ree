import type React from "react";
import styles from "./GlassPage.module.css";

/**
 * The outer two elements every glass page opens with: the scrollable page and
 * the framed board inside it.
 *
 * `.pageRoot` is also the glass surface boundary. A primitive rendered inside
 * one of these pages resolves the shared roles — controls, fields, surfaces —
 * to their glass values by inheritance, rather than by taking a variant.
 */
export function GlassPageShell({
  children,
  variant = "framed",
}: {
  children: React.ReactNode;
  /** `docked` is a page opened inside the canvas, which paints its own ground
   * and wants no board of its own. */
  variant?: "framed" | "docked";
}) {
  return (
    <div className={styles.pageRoot} data-variant={variant === "docked" ? "docked" : undefined}>
      {variant === "framed" ? <div className={styles.pageFrame}>{children}</div> : children}
    </div>
  );
}

/** The two-column body most step pages use: content, then a narrow aside. */
export function GlassMainGrid({ children }: { children: React.ReactNode }) {
  return <div className={styles.mainGrid}>{children}</div>;
}

/** The aside column's stack. */
export function GlassAside({ children }: { children: React.ReactNode }) {
  return <aside className={styles.aside}>{children}</aside>;
}

/**
 * A glass panel. `clipped` is for panels whose body scrolls or whose corners
 * would otherwise be overrun by a footer welded to the bottom.
 */
export function GlassPanel({
  children,
  clipped = false,
  density,
}: {
  children: React.ReactNode;
  clipped?: boolean;
  /** `compact` pads the panel itself, for asides that hold one block rather
   * than a page section with its own body. */
  density?: "compact";
}) {
  return (
    <section className={styles.panel} data-clipped={clipped || undefined} data-density={density}>
      {children}
    </section>
  );
}

/** The padded interior of a panel. */
export function GlassSectionBody({ children }: { children: React.ReactNode }) {
  return <div className={styles.sectionBody}>{children}</div>;
}
