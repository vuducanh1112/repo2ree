import type React from "react";
import { useRef, useState } from "react";
import { Ic } from "../../components/Icon";
import { LEVELS } from "../../constants/levels";
import { APP_PAGE } from "../../constants/pages";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverColor,
  S_ACTION_BUTTON_BASE,
  S_FLEX_ROW_GAP_8,
  S_SECTION_LABEL,
} from "../../constants/theme";
import type { AppPage } from "../../types";

export interface LandingViewProps {
  onLoad: (page: AppPage) => void;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function LandingView({ onLoad }: LandingViewProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const go = async () => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setLoading(false);
    onLoad(APP_PAGE.EXPLORER);
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
          <label
            htmlFor="repo-url-input"
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.4,
            }}
          >
            Repository URL
          </label>
          <div style={S_FLEX_ROW_GAP_8}>
            <div style={{ flex: 1, position: "relative" }}>
              <div
                style={{
                  position: "absolute",
                  left: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: C.textMuted,
                }}
              >
                {Ic.link()}
              </div>
              <input
                id="repo-url-input"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && url.trim() && go()}
                placeholder="https://github.com/org/repo"
                style={{
                  width: "100%",
                  border: `1.5px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 10px 8px 32px",
                  fontSize: 14,
                  fontFamily: F.mono,
                  color: C.text,
                  background: C.bg,
                }}
              />
            </div>
            <button
              type="button"
              onClick={go}
              disabled={loading}
              style={{
                ...actionBtn({
                  border: "none",
                  borderRadius: 8,
                  padding: "8px 16px",
                  fontSize: 14,
                  fontWeight: 600,
                  background: C.accent,
                  color: "#fff",
                  transition: "all 0.12s",
                }),
                background: C.accent,
                color: "#fff",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 5,
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  display: "flex",
                  animation: loading ? "spin 0.9s linear infinite" : "none",
                }}
              >
                {loading ? Ic.loader() : Ic.play()}
              </span>
              {loading ? "…" : "Load"}
            </button>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1, height: 1, background: C.border }} />
            <span style={{ fontSize: 12, color: C.textMuted, fontFamily: F.mono }}>or</span>
            <div style={{ flex: 1, height: 1, background: C.border }} />
          </div>
          <input
            ref={fileRef}
            type="file"
            style={{ display: "none" }}
            onChange={(event) => {
              if (event.target.files?.[0]) go();
            }}
            accept=".zip,.tar,.tar.gz"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            style={{
              background: C.bg,
              border: `1.5px dashed ${C.borderMid}`,
              borderRadius: 10,
              padding: 16,
              cursor: "pointer",
              width: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 5,
              transition: "border-color 0.15s, background 0.15s",
            }}
            {...hoverBorderColor(C.accent, C.borderMid)}
            {...hoverBg(C.accentBg, C.bg)}
          >
            <span style={{ color: C.accent }}>{Ic.upload()}</span>
            <span style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans }}>
              Drop archive or <span style={{ color: C.accent }}>browse</span>
            </span>
            <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono }}>
              .zip · .tar · .tar.gz
            </span>
          </button>
          <button
            type="button"
            onClick={() => onLoad(APP_PAGE.EXPLORER)}
            disabled={loading}
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
            ✦ Try with demo repository (Author)
          </button>
          <button
            type="button"
            onClick={() => onLoad(APP_PAGE.REVIEWER)}
            disabled={loading}
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
            ✦ Review a sealed pod (Reviewer)
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
