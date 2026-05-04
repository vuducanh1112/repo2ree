import { Ic } from "../../shared/components/Icon";
import { F } from "../../theme/theme";

interface RvVerdictBannerProps {
  allDone: boolean;
}

export function RvVerdictBanner({ allDone }: RvVerdictBannerProps) {
  if (!allDone) return null;
  return (
    <div
      style={{
        background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
        border: "1.5px solid #22c55e40",
        borderRadius: 12,
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        boxShadow: "0 0 0 4px #22c55e10, 0 4px 20px rgba(34,197,94,0.12)",
        animation: "fadeUp 0.3s ease",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#22c55e",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          boxShadow: "0 0 0 6px #22c55e20",
        }}
      >
        {Ic.check(18)}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "#15803d",
            fontFamily: F.sans,
            marginBottom: 2,
          }}
        >
          Reactivation Verified — Reproducible ✓
        </div>
        <div style={{ fontSize: 13, color: "#166534", fontFamily: F.sans }}>
          All four stages passed. The sealed REE is byte-for-byte reproducible on this machine.
        </div>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 3,
          alignItems: "flex-end",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 11, color: "#166534", fontFamily: F.mono, fontWeight: 600 }}>
          {new Date().toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        <span style={{ fontSize: 10, color: "#16a34a", fontFamily: F.sans }}>by reviewer</span>
      </div>
    </div>
  );
}
