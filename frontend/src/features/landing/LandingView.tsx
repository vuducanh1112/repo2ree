import type React from "react";
import { useState } from "react";
import { ApiClient } from "../../api/client";
import { WorkspaceApi } from "../../api/workspaces";
import { Ic } from "../../components/Icon";
import { LEVELS } from "../../constants/levels";
import { APP_ROUTE, type AppLoadRoutePath } from "../../constants/pages";
import {
  C,
  F,
  hoverBg,
  hoverColor,
  S_ACTION_BUTTON_BASE,
  S_SECTION_LABEL,
} from "../../constants/theme";

interface LandingViewProps {
  onLoad: (path: AppLoadRoutePath) => void;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function LandingView({ onLoad }: LandingViewProps) {
  const [loadingCreate, setLoadingCreate] = useState(false);

  const createRee = async () => {
    setLoadingCreate(true);
    try {
      const env =
        (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
      const client = new ApiClient({
        baseUrl: env.VITE_API_BASE_URL || "",
      });
      const workspaceApi = new WorkspaceApi(client);
      const workspace = await workspaceApi.createWorkspace({
        sourceMode: "upload",
        name: "Explorer Workspace",
      });
      onLoad(`${APP_ROUTE.EXPLORER}?reeId=${encodeURIComponent(workspace.reeId)}`);
    } catch {
      onLoad(APP_ROUTE.EXPLORER);
    } finally {
      setLoadingCreate(false);
    }
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
            REE Explorer
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
            onClick={() => {
              void createRee();
            }}
            disabled={loadingCreate}
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
            <span
              style={{
                display: "flex",
                animation: loadingCreate ? "spin 0.9s linear infinite" : "none",
              }}
            >
              {loadingCreate ? Ic.loader() : Ic.play()}
            </span>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              {loadingCreate ? "Creating…" : "Create REE"}
            </span>
          </button>
          <button
            type="button"
            onClick={() => onLoad(APP_ROUTE.REVIEWER)}
            disabled={loadingCreate}
            style={{
              ...actionBtn({
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: 8,
                background: "transparent",
                color: C.textMid,
                fontWeight: 400,
                transition: "background 0.13s, color 0.13s",
              }),
              background: "transparent",
              cursor: "pointer",
              width: "100%",
              color: C.textMid,
            }}
            {...hoverBg(C.surfaceAlt, "transparent")}
            {...hoverColor(C.text, C.textMid)}
          >
            Review REE
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
          {LEVELS.map((l) => (
            <div
              key={l.n}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: l.color }} />L
              {l.n} {l.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
