import { AXES } from "@core/evaluate/axes";
import type React from "react";
import { APP_ROUTE, type AppLoadRoutePath, LOAD_REE_PARAM } from "../app-shell/state/pages";
import { Ic } from "../shared/components/Icon";
import { C, F, S_ACTION_BUTTON_BASE, S_SECTION_LABEL } from "../theme/theme";

interface LandingViewProps {
  onLoad: (path: AppLoadRoutePath) => void;
  onViewAgents: () => void;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function LandingView({ onLoad, onViewAgents }: LandingViewProps) {
  // Both entry points run the same creation flow: pick a lab location (agent),
  // then the workbench step — which is also where an existing REE bundle is
  // loaded, since the load runs on the workbench that step provisions.
  const createRee = () => {
    onLoad(APP_ROUTE.LAB_LOCATION);
  };
  const loadRee = () => {
    onLoad(`${APP_ROUTE.LAB_LOCATION}?${LOAD_REE_PARAM}=1`);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 430, width: "100%", animation: "fadeUp 0.4s ease" }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 50,
              height: 50,
              borderRadius: 13,
              background: C.accentBg,
              border: `1px solid ${C.accentBorder}`,
              color: C.accent,
              marginBottom: 14,
            }}
          >
            {Ic.layers(22)}
          </div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 600,
              color: C.text,
              letterSpacing: -0.5,
              marginBottom: 6,
            }}
          >
            REE Workspace
          </h1>
          <p style={{ fontSize: 14, color: C.textMid, lineHeight: 1.6 }}>
            Build, inspect, and certify
            <br />
            Reproducible Execution Environments
          </p>
        </div>
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 14,
            padding: 22,
            boxShadow: "0 2px 12px rgba(0,0,0,0.05)",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.4,
            }}
          >
            Choose Action
          </div>
          <button
            type="button"
            onClick={createRee}
            style={{
              ...actionBtn({
                border: "none",
                borderRadius: 8,
                padding: "10px 16px",
                fontSize: 14,
                fontWeight: 600,
                background: C.accent,
                color: "#fff",
                transition: "all 0.12s",
              }),
              borderRadius: 10,
              background: C.accent,
              color: "#fff",
              cursor: "pointer",
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 5,
              justifyContent: "center",
            }}
          >
            <span style={{ display: "flex" }}>{Ic.play()}</span>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Create REE</span>
          </button>
          <button
            type="button"
            onClick={loadRee}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              width: "100%",
              borderRadius: 10,
              padding: "9px 16px",
              background: "transparent",
              border: `1px solid ${C.border}`,
              color: C.textMid,
              fontSize: 13,
              fontWeight: 500,
              fontFamily: F.sans,
              cursor: "pointer",
            }}
          >
            <span style={{ display: "flex" }}>{Ic.upload(15)}</span>
            Load REE
          </button>
          <button
            type="button"
            onClick={onViewAgents}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              width: "100%",
              borderRadius: 10,
              padding: "9px 16px",
              background: "transparent",
              border: `1px solid ${C.border}`,
              color: C.textMid,
              fontSize: 13,
              fontWeight: 500,
              fontFamily: F.sans,
              cursor: "pointer",
            }}
          >
            <span style={{ display: "flex" }}>{Ic.cpu(15)}</span>
            View Agents
          </button>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 12,
            marginTop: 20,
            flexWrap: "wrap",
          }}
        >
          {AXES.map((axis) => (
            <div
              key={axis.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: axis.color }} />
              {axis.label} ({axis.steps.join(" → ")})
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
