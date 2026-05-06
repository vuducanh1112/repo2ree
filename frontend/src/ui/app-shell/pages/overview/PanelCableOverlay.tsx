import React, { useRef } from "react";
import type { ReeEditorViewModel } from "../../../../application/ree-editor/reeEditorViewModel";
import type { Badges } from "../../../../core/ree/ReeTypes";
import { LEVELS } from "../../../../core/review/levels";
import { type CableGeo, measureCableGeo, type PanelRefs } from "./PanelCableOverlayHelpers";
import { CableOverlaySvg } from "./PanelCableOverlaySections";

interface PanelCableOverlayProps extends PanelRefs {
  containerRef: React.RefObject<HTMLDivElement>;
  podSvgRef: React.RefObject<SVGSVGElement>;
  level: number;
  badges: Badges;
  ree: ReeEditorViewModel;
}

export function PanelCableOverlay(props: PanelCableOverlayProps) {
  const levelMeta = LEVELS[Math.min(props.level, 7)];
  const [geo, setGeo] = React.useState<CableGeo | null>(null);
  const rafRef = useRef<number | null>(null);

  const measure = React.useCallback(() => {
    const container = props.containerRef.current;
    const podSvg = props.podSvgRef.current;
    if (!container || !podSvg) return;

    const nextGeo = measureCableGeo({
      container,
      podSvg,
      refs: props,
      ree: props.ree,
      badges: props.badges,
    });
    if (nextGeo) setGeo(nextGeo);
  }, [props]);

  React.useEffect(() => {
    rafRef.current = requestAnimationFrame(measure);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [measure]);

  React.useEffect(() => {
    const panelRefs = [
      props.sourceRef,
      props.runtimeRef,
      props.metadataRef,
      props.swhRef,
      props.evaluateRef,
      props.sbomRef,
      props.sealRef,
      props.archiveRef,
      props.activationRef,
      props.hbomRef,
    ];
    const targets = [props.containerRef, ...panelRefs] as React.RefObject<Element>[];
    const ro = new ResizeObserver(() => {
      rafRef.current = requestAnimationFrame(measure);
    });

    targets.forEach((targetRef) => {
      if (targetRef.current) ro.observe(targetRef.current);
    });
    return () => ro.disconnect();
  });

  if (!geo) return null;
  return <CableOverlaySvg geo={geo} levelMeta={levelMeta} />;
}
