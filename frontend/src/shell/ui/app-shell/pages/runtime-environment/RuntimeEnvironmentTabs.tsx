import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgSegmentedTab } from "../../../theme/lightGlassTheme";
import { type AppShellPage, PAGE } from "../../state/pages";

type RuntimeEnvTab = typeof PAGE.BUILD | typeof PAGE.SBOM;

interface RuntimeEnvironmentTabsProps {
  active: RuntimeEnvTab;
  buildReady: boolean;
  sbomReady: boolean;
  onGo?: (key: AppShellPage) => void;
}

export function RuntimeEnvironmentTabs({
  active,
  buildReady,
  sbomReady,
  onGo,
}: RuntimeEnvironmentTabsProps) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
        marginBottom: 18,
      }}
    >
      <RuntimeEnvironmentTab
        active={active === PAGE.BUILD}
        ready={buildReady}
        icon={Ic.cpu(14)}
        label="Build Runtime"
        onClick={() => onGo?.(PAGE.BUILD)}
      />
      <RuntimeEnvironmentTab
        active={active === PAGE.SBOM}
        ready={sbomReady}
        icon={Ic.package(14)}
        label="Generate SBOM"
        onClick={() => onGo?.(PAGE.SBOM)}
      />
    </div>
  );
}

function RuntimeEnvironmentTab({
  active,
  ready,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  ready: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active} style={lgSegmentedTab(active)}>
      <span style={{ display: "flex" }}>{icon}</span>
      <span>{label}</span>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: 99,
          background: ready ? lgColors.success : "rgba(148, 163, 184, 0.58)",
          boxShadow: ready ? "0 0 0 3px rgba(34, 197, 94, 0.13)" : "none",
        }}
      />
    </button>
  );
}
