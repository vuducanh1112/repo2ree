import { C } from "../../theme/theme";

/**
 * Decorative, non-interactive lab atmosphere behind the pod: drifting ambient
 * light pools, an overhead glass light bar, a slow scanning sheen, and a frosted
 * workbench surface the pod is seated on. Pure CSS, pointer-events disabled.
 */
export function LabBackdrop() {
  return (
    <div
      aria-hidden
      style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}
    >
      {/* drifting ambient light pools */}
      <div
        style={{
          position: "absolute",
          left: "10%",
          top: "12%",
          width: 420,
          height: 420,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(56,189,248,0.20) 0%, rgba(56,189,248,0) 70%)",
          filter: "blur(8px)",
          animation: "labDriftA 16s ease-in-out infinite",
        }}
      />
      <div
        style={{
          position: "absolute",
          right: "8%",
          top: "8%",
          width: 380,
          height: 380,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(129,140,248,0.18) 0%, rgba(129,140,248,0) 70%)",
          filter: "blur(8px)",
          animation: "labDriftB 20s ease-in-out infinite",
        }}
      />

      {/* overhead glass light bar casting a soft beam onto the bench */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: 0,
          width: 320,
          height: 14,
          transform: "translateX(-50%)",
          borderRadius: "0 0 12px 12px",
          background: "linear-gradient(180deg, rgba(255,255,255,0.9), rgba(186,230,253,0.5))",
          border: `1px solid ${C.border}`,
          borderTop: "none",
          boxShadow: "0 8px 30px rgba(56,189,248,0.35)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: 14,
          width: 520,
          height: "62%",
          transform: "translateX(-50%)",
          background: "linear-gradient(180deg, rgba(186,230,253,0.28) 0%, rgba(186,230,253,0) 78%)",
          clipPath: "polygon(38% 0, 62% 0, 100% 100%, 0 100%)",
        }}
      />

      {/* slow scanning sheen for a sense of a live instrument */}
      <div
        style={{
          position: "absolute",
          inset: "0 0 auto 0",
          height: "45%",
          background:
            "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(224,242,254,0.5) 50%, rgba(255,255,255,0) 100%)",
          animation: "labScan 11s ease-in-out infinite",
        }}
      />

      {/* frosted workbench surface the pod is seated on */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: "34%",
          background:
            "linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(241,245,249,0.55) 45%, rgba(226,232,240,0.85) 100%)",
          borderTop: `1px solid ${C.border}`,
          backdropFilter: "blur(1px)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.7)",
        }}
      />
    </div>
  );
}
