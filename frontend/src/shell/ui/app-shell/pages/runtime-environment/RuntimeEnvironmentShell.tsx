import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { lgPageColors, lgStyles } from "../../../theme/lightGlassTheme";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import type { AppShellPage, PAGE } from "../../state/pages";
import { RuntimeEnvironmentTabs } from "./RuntimeEnvironmentTabs";

export const RUNTIME_ENV_COLOR = lgPageColors.runtimeEnv;

interface RuntimeEnvironmentShellProps {
  active: typeof PAGE.BUILD | typeof PAGE.SBOM | typeof PAGE.ACTIVATION;
  buildReady: boolean;
  sbomReady: boolean;
  activationReady: boolean;
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
  activationReady,
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
          subtitle="Build the executable environment, generate the software inventory, and verify startup."
          badges={headerBadges}
          right={headerRight}
        />

        <RuntimeEnvironmentTabs
          active={active}
          buildReady={buildReady}
          sbomReady={sbomReady}
          activationReady={activationReady}
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
