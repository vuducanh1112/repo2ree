import { AXES } from "@core/evaluate/axes";
import type React from "react";
import { APP_ROUTE, type AppLoadRoutePath } from "../app-shell/state/pages";
import { Ic } from "../shared/components/Icon";
import { C, F, S_ACTION_BUTTON_BASE, S_SECTION_LABEL } from "../theme/theme";

interface LandingViewProps {
  onLoad: (path: AppLoadRoutePath) => void;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function LandingView({ onLoad }: LandingViewProps) {
  const createRee = () => {
    // Provisioning is deferred to the Workbench step inside the editor.
    onLoad(APP_ROUTE.WORKSPACE);
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
