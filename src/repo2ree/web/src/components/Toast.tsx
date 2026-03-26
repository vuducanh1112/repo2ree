import { useEffect } from "react";
import { F } from "../constants/theme";
import { Ic } from "./Icon";

interface ToastProps {
  message: string;
  type: "info" | "success" | "error";
  onClose: () => void;
}

const typeConfig = {
  info: { bg: "#dbeafe", border: "#93c5fd", color: "#0369a1", icon: Ic.info },
  success: { bg: "#dcfce7", border: "#86efac", color: "#15803d", icon: Ic.check },
  error: { bg: "#fee2e2", border: "#fca5a5", color: "#991b1b", icon: Ic.x },
};

export function Toast({ message, type, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const config = typeConfig[type];

  return (
    <div
      style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        padding: 12,
        paddingLeft: 14,
        backgroundColor: config.bg,
        border: `1px solid ${config.border}`,
        borderRadius: 6,
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 13,
        fontFamily: F.sans,
        color: config.color,
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
        animation: "slideUp 0.3s ease",
        maxWidth: 400,
        zIndex: 9999,
      }}
    >
      <div style={{ color: config.color, flexShrink: 0, display: "flex" }}>{config.icon(16)}</div>
      <span>{message}</span>
      <button
        type="button"
        onClick={onClose}
        style={{
          marginLeft: "auto",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "inherit",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          padding: 0,
        }}
      >
        {Ic.x(14)}
      </button>
    </div>
  );
}
