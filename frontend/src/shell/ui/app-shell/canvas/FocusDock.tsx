import { type ReactNode, useEffect } from "react";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { PodWidget } from "../pages/overview/PodWidget";
import type { CanvasNode } from "./canvasNodes";

interface FocusDockProps {
  node: CanvasNode | undefined;
  evaluation: EvaluationState;
  /** Whether the dock can be dismissed (false while the workbench is unprovisioned). */
  closable: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function FocusDock({ node, evaluation, closable, onClose, children }: FocusDockProps) {
  useEffect(() => {
    if (!closable) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closable, onClose]);

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 20, display: "flex" }}>
      <button
        type="button"
        aria-label="Back to constellation"
        onClick={() => closable && onClose()}
        style={{
          position: "absolute",
          inset: 0,
          border: "none",
          background: "rgba(225,230,238,0.62)",
          backdropFilter: "blur(3px)",
          cursor: closable ? "pointer" : "default",
        }}
      />

      <div
        style={{
          position: "relative",
          flex: "0 0 32%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 14,
          zIndex: 1,
          pointerEvents: "none",
        }}
      >
        <PodWidget evaluation={evaluation} size={230} />
        {node && (
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 11,
              color: C.textMid,
              textAlign: "center",
              lineHeight: 1.6,
              maxWidth: 240,
            }}
          >
            the specimen stays anchored —
            <br />
            <b style={{ color: C.text }}>{node.label}</b> is wired in beside it
          </div>
        )}
      </div>

      <div
        style={{
          position: "relative",
          flex: 1,
          display: "flex",
          alignItems: "stretch",
          padding: "22px 26px 22px 0",
          zIndex: 1,
        }}
      >
        <div
          style={{
            position: "relative",
            display: "flex",
            flex: 1,
            minWidth: 0,
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            overflow: "hidden",
            boxShadow: "0 24px 60px rgba(13,17,23,0.18)",
            animation: "dockIn 0.4s cubic-bezier(0.4,0,0.2,1)",
          }}
        >
          {/* tether linking the dock back to the pod */}
          <div
            style={{
              position: "absolute",
              left: -26,
              top: "50%",
              width: 26,
              height: 2,
              background: C.accent,
              opacity: 0.55,
              boxShadow: `0 0 8px ${C.accent}`,
            }}
          />
          {closable && (
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              style={{
                position: "absolute",
                top: 12,
                right: 12,
                zIndex: 2,
                width: 30,
                height: 30,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                background: C.surface,
                color: C.textMuted,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {Ic.x(15)}
            </button>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}
