import { C, F } from "../../../theme/theme";

interface FieldSectionProps {
  title: string;
  icon?: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  filledCount: number;
  totalCount: number;
}
export function FieldSection({
  title,
  icon,
  subtitle,
  children,
  filledCount,
  totalCount,
}: FieldSectionProps) {
  const allFilled = filledCount === totalCount && totalCount > 0;
  const someFilled = filledCount > 0;
  const pct = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0;
  return (
    <div
      style={{
        ...{
          background: C.surface,
          borderRadius: 10,
          overflow: "hidden",
          transition: "border-color 0.3s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        },
        border: `1px solid ${allFilled ? "#22c55e40" : C.border}`,
      }}
    >
      <div
        style={{
          ...{
            padding: "11px 20px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "background 0.3s",
          },
          borderBottom: `1px solid ${allFilled ? "#22c55e30" : C.border}`,
          background: allFilled ? "#f0fdf4" : "#fafbfd",
        }}
      >
        <div
          style={{
            ...{
              width: 3,
              height: 16,
              borderRadius: 99,
              flexShrink: 0,
              transition: "background 0.3s",
            },
            background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
          }}
        />
        {icon && (
          <span
            style={{
              ...{
                display: "flex",
              },
              color: allFilled ? "#16a34a" : C.textMuted,
            }}
          >
            {icon}
          </span>
        )}
        <span
          style={{
            ...{
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: 1,
              textTransform: "uppercase",
              fontFamily: F.sans,
            },
            color: allFilled ? "#15803d" : C.text,
          }}
        >
          {title}
        </span>
        {subtitle && (
          <span
            style={{
              fontSize: 12,
              color: C.textMuted,
              fontWeight: 400,
              textTransform: "none",
              letterSpacing: 0,
            }}
          >
            {typeof subtitle === "string" ? `— ${subtitle}` : subtitle}
          </span>
        )}
        <div
          style={{
            flex: 1,
          }}
        />
        {totalCount > 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <div
              style={{
                width: 40,
                height: 3,
                borderRadius: 99,
                background: C.border,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
                  borderRadius: 99,
                  transition: "width 0.4s",
                }}
              />
            </div>
            <span
              style={{
                ...{
                  fontSize: 11,
                  fontFamily: F.mono,
                  fontWeight: 600,
                },
                color: allFilled ? "#16a34a" : someFilled ? "#92400e" : C.textMuted,
              }}
            >
              {filledCount}/{totalCount}
            </span>
          </div>
        )}
      </div>
      <div
        style={{
          padding: "0 20px",
        }}
      >
        {children}
      </div>
    </div>
  );
}
