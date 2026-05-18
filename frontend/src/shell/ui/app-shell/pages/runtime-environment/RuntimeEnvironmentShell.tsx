import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgStyles } from "../../../theme/lightGlassTheme";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import type { AppShellPage, PAGE } from "../../state/pages";
import { RuntimeEnvironmentTabs } from "./RuntimeEnvironmentTabs";

// Shared section colour for the Runtime Environment chrome and its sub-pages —
// kept stable across the Build and SBOM tabs so the section reads as one unit.
export const RUNTIME_ENV_COLOR = lgColors.cyan;

interface RuntimeEnvironmentShellProps {
  active: typeof PAGE.BUILD | typeof PAGE.SBOM;
  buildReady: boolean;
  sbomReady: boolean;
  onGo?: (key: AppShellPage) => void;
  headerBadges: React.ReactNode;
  headerRight?: React.ReactNode;
  main: React.ReactNode;
  aside: React.ReactNode;
}

export function RuntimeEnvironmentShell({
  active,
  buildReady,
  sbomReady,
  onGo,
  headerBadges,
  headerRight,
  main,
  aside,
}: RuntimeEnvironmentShellProps) {
  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.cpu(24)}
          iconTint={{
            color: RUNTIME_ENV_COLOR,
            border: `${RUNTIME_ENV_COLOR}55`,
            shadow: `${RUNTIME_ENV_COLOR}28`,
          }}
          title="Runtime Environment"
          subtitle="Build the executable environment and generate the software inventory from it."
          badges={headerBadges}
          right={headerRight}
        />

        <RuntimeEnvironmentTabs
          active={active}
          buildReady={buildReady}
          sbomReady={sbomReady}
          onGo={onGo}
        />

        <div style={lgStyles.mainGrid}>
          {main}
          <aside style={lgStyles.aside}>{aside}</aside>
        </div>
      </div>
    </div>
  );
}
