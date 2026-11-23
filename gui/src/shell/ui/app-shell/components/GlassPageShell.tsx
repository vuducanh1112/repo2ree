import type React from "react";
import styles from "./GlassPage.module.css";

export function GlassPageShell({
  children,
  variant = "framed",
}: {
  children: React.ReactNode;
  variant?: "framed" | "docked";
}) {
  return (
    <div className={styles.pageRoot} data-variant={variant === "docked" ? "docked" : undefined}>
      {variant === "framed" ? <div className={styles.pageFrame}>{children}</div> : children}
    </div>
  );
}

export function GlassMainGrid({ children }: { children: React.ReactNode }) {
  return <div className={styles.mainGrid}>{children}</div>;
}

export function GlassAside({ children }: { children: React.ReactNode }) {
  return <aside className={styles.aside}>{children}</aside>;
}

export function GlassPanel({
  children,
  clipped = false,
  density,
}: {
  children: React.ReactNode;
  clipped?: boolean;
  density?: "compact";
}) {
  return (
    <section className={styles.panel} data-clipped={clipped || undefined} data-density={density}>
      {children}
    </section>
  );
}

export function GlassSectionBody({ children }: { children: React.ReactNode }) {
  return <div className={styles.sectionBody}>{children}</div>;
}
