import { Ic } from "../../../../../shared/components/Icon";
import { C, F } from "../../../../../theme/theme";

interface SealConfirmHeaderProps {
  color: string;
}

export function SealConfirmHeader({ color }: SealConfirmHeaderProps) {
  return (
    <div
      style={{
        padding: "16px 20px 12px",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            ...{
              width: 32,
              height: 32,
              borderRadius: 8,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            },
            background: `${color}18`,
          }}
        >
          <span
            style={{
              ...{
                display: "flex",
              },
              color,
            }}
          >
            {Ic.lock(16)}
          </span>
        </div>
        <div>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              fontFamily: F.sans,
              color: C.text,
            }}
          >
            Seal this REE?
          </div>
          <div
            style={{
              fontSize: 11,
              fontFamily: F.sans,
              color: C.textMuted,
              marginTop: 1,
            }}
          >
            This action cannot be undone.
          </div>
        </div>
      </div>
    </div>
  );
}
