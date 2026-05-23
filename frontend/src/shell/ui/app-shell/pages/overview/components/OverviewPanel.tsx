import type React from "react";
import { Ic } from "../../../../shared/components/Icon";
import {
  type LgStageTint,
  lgPanelNavButton,
  lgStageDot,
  lgStyles,
} from "../../../../theme/lightGlassTheme";
import { hoverBrightness } from "../../../../theme/theme";

interface OverviewPanelProps {
  panelRef?: React.RefObject<HTMLDivElement>;
  tint: LgStageTint;
  title: string;
  /** Whether this stage has been provided/connected — drives the header dot glow. */
  active: boolean;
  /** Optional control rendered at the far right of the header (e.g. an include toggle). */
  headerRight?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/**
 * Glass "stage" card used across the Overview dashboard. Each card carries its
 * stage hue (tint) on the status dot and footer button so the panel, its cable
 * to the pod, and the sidebar all read as one colour.
 */
export function OverviewPanel({
  panelRef,
  tint,
  title,
  active,
  headerRight,
  children,
  footer,
}: OverviewPanelProps) {
  return (
    <div ref={panelRef} style={lgStyles.overviewPanel}>
      <div style={lgStyles.overviewPanelHeaderRow}>
        <div style={lgStageDot(tint.line, active)} />
        <span style={lgStyles.overviewPanelLabel}>{title}</span>
        {headerRight}
      </div>
      <div style={lgStyles.overviewPanelFields}>{children}</div>
      {footer && <div style={lgStyles.overviewPanelFooter}>{footer}</div>}
    </div>
  );
}

interface OverviewNavButtonProps {
  tint: LgStageTint;
  label: string;
  onClick: () => void;
}

/** Footer call-to-action that jumps to the stage's full editor page. */
export function OverviewNavButton({ tint, label, onClick }: OverviewNavButtonProps) {
  return (
    <button type="button" onClick={onClick} style={lgPanelNavButton(tint)} {...hoverBrightness(96)}>
      {label}
      <span style={{ display: "flex" }}>{Ic.chevR(12)}</span>
    </button>
  );
}
