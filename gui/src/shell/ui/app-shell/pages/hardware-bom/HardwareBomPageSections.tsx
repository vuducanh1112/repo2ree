import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgContentCard, lgStatusBadge, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import type React from "react";
import type { HardwareColumn } from "./hardwareBomColumns";
import { actionBtn } from "./hardwareBomPageHelpers";

export interface CategoryDescriptor {
  key: "cpus" | "gpus" | "memory" | "storage" | "network";
  label: string;
  singular: string;
  addLabel: string;
  icon: React.ReactNode;
  subtitle: string;
}

export function HardwareCategoryTabs({
  categories,
  counts,
  activeKey,
  onSelect,
}: {
  categories: CategoryDescriptor[];
  counts: Record<CategoryDescriptor["key"], number>;
  activeKey: CategoryDescriptor["key"];
  onSelect: (key: CategoryDescriptor["key"]) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        marginBottom: 16,
      }}
    >
      {categories.map((category) => {
        const active = activeKey === category.key;
        const count = counts[category.key];
        return (
          <button
            key={category.key}
            type="button"
            onClick={() => onSelect(category.key)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              border: active
                ? "1px solid rgba(14, 165, 233, 0.45)"
                : "1px solid rgba(148, 163, 184, 0.34)",
              background: active ? "rgba(239, 246, 255, 0.92)" : "rgba(255, 255, 255, 0.62)",
              color: active ? lgColors.primaryDeep : lgColors.textMid,
              padding: "7px 12px",
              borderRadius: 999,
              cursor: "pointer",
              fontFamily: F.sans,
              fontSize: 12,
              fontWeight: 700,
              boxShadow: active
                ? "0 6px 16px rgba(14, 165, 233, 0.16)"
                : "inset 0 1px 0 rgba(255, 255, 255, 0.92)",
            }}
          >
            <span style={{ display: "flex", color: active ? lgColors.blue : lgColors.textMuted }}>
              {category.icon}
            </span>
            {category.label}
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: active ? lgColors.primaryDeep : lgColors.textMuted,
                background: "rgba(255, 255, 255, 0.85)",
                borderRadius: 999,
                padding: "1px 7px",
                border: "1px solid rgba(148, 163, 184, 0.28)",
              }}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function HardwareTableCard<RowT extends { id: string }>({
  category,
  rows,
  columns,
  locked,
  onAdd,
  onRemove,
}: {
  category: CategoryDescriptor;
  rows: RowT[];
  columns: HardwareColumn<RowT>[];
  locked: boolean;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  const gridTemplateColumns = `${columns.map((column) => column.width).join(" ")} auto`;

  return (
    <div style={lgContentCard(0)}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: lgColors.blue, display: "flex" }}>{category.icon}</span>
          <div>
            <div style={{ ...lgStyles.label, gap: 6 }}>{category.label}</div>
            <div style={lgStyles.helper}>{category.subtitle}</div>
          </div>
        </div>
        <span style={lgStatusBadge(rows.length > 0)}>
          {rows.length} {rows.length === 1 ? category.singular : category.label.toLowerCase()}
        </span>
      </div>

      {rows.length === 0 ? (
        <div
          style={{
            ...lgStyles.helper,
            textAlign: "center",
            padding: "18px 12px",
            border: "1px dashed rgba(148, 163, 184, 0.45)",
            borderRadius: 8,
            background: "rgba(248, 250, 252, 0.55)",
          }}
        >
          No {category.label.toLowerCase()} recorded yet.{" "}
          {locked ? "Unlock to add." : `Use "${category.addLabel}" or Profile This Machine.`}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns,
              gap: 8,
              alignItems: "center",
              padding: "0 10px",
            }}
          >
            {columns.map((column) => (
              <div
                key={column.key}
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: 0.4,
                  textTransform: "uppercase",
                  color: lgColors.textMuted,
                  fontFamily: F.sans,
                }}
              >
                {column.label}
              </div>
            ))}
            <div />
          </div>
          {rows.map((row, index) => (
            <div
              key={row.id}
              style={{
                border: "1px solid rgba(148, 163, 184, 0.32)",
                borderRadius: 9,
                background: "rgba(255, 255, 255, 0.7)",
                padding: 10,
                boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.92)",
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns,
                  gap: 8,
                  alignItems: "center",
                }}
              >
                {columns.map((column) => (
                  <div key={column.key}>{column.render(row, index)}</div>
                ))}
                {!locked ? (
                  <button
                    type="button"
                    onClick={() => onRemove(index)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: lgColors.textMuted,
                      padding: 4,
                      display: "flex",
                      borderRadius: 5,
                    }}
                    aria-label={`Remove ${category.singular}`}
                  >
                    {Ic.x()}
                  </button>
                ) : (
                  <div />
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!locked && (
        <div style={{ marginTop: 12 }}>
          <button
            type="button"
            onClick={onAdd}
            style={{
              ...actionBtn({
                border: "1.5px dashed rgba(148, 163, 184, 0.5)",
                padding: "7px 12px",
                background: "transparent",
                color: lgColors.textMid,
              }),
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              cursor: "pointer",
              borderRadius: 8,
            }}
          >
            {Ic.plus()} {category.addLabel}
          </button>
        </div>
      )}
    </div>
  );
}
