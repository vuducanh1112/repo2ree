import { C, F } from "../../../../../theme/theme";

interface SealConfirmCopyProps {
  allLive: boolean;
  level: number;
  totalCables: number;
  currentLabel: string;
}

export function SealConfirmCopy({
  allLive,
  level,
  totalCables,
  currentLabel,
}: SealConfirmCopyProps) {
  return (
    <div
      style={{
        padding: "12px 20px",
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontFamily: F.sans,
          color: C.textMid,
          lineHeight: 1.6,
        }}
      >
        {allLive ? (
          <>
            All <strong>{totalCables}</strong> panels are connected. The REE will be frozen at{" "}
            <strong>
              L{level} · {currentLabel}
            </strong>{" "}
            and become read-only.
          </>
        ) : (
          <>
            Sealing now will freeze the REE at{" "}
            <strong>
              L{level} · {currentLabel}
            </strong>{" "}
            with incomplete data. You can still seal, but the missing panels will not be part of the
            record.
          </>
        )}
      </div>
    </div>
  );
}
