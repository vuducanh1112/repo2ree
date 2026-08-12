import { Badge } from "@shell/ui/shared/components/Badge";
import { Caption } from "@shell/ui/shared/components/Caption";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import type React from "react";
import styles from "./HardwareBomPage.module.css";
import type { HardwareColumn } from "./hardwareBomColumns";

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
    <div className={styles.categories}>
      {categories.map((category) => {
        const active = activeKey === category.key;
        const count = counts[category.key];
        return (
          <button
            key={category.key}
            type="button"
            onClick={() => onSelect(category.key)}
            aria-pressed={active}
            className={styles.category}
          >
            <span aria-hidden className={styles.categoryIcon}>
              {category.icon}
            </span>
            {category.label}
            <span className={styles.categoryCount}>{count}</span>
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
    <Surface spacing="flush" vars={{ "--table-columns": gridTemplateColumns }}>
      <div className={styles.tableHead}>
        <div className={styles.tableIdentity}>
          <span aria-hidden className={styles.tableIcon}>
            {category.icon}
          </span>
          <Caption title={category.label} hint={category.subtitle} />
        </div>
        <Badge tone={rows.length > 0 ? "success" : "warning"}>
          {rows.length} {rows.length === 1 ? category.singular : category.label.toLowerCase()}
        </Badge>
      </div>

      {rows.length === 0 ? (
        <div className={styles.empty}>
          No {category.label.toLowerCase()} recorded yet.{" "}
          {locked ? "Unlock to add." : `Use "${category.addLabel}" or Profile This Machine.`}
        </div>
      ) : (
        <div className={styles.rows}>
          <div className={`${styles.grid} ${styles.columnHeaders}`}>
            {columns.map((column) => (
              <div key={column.key} className={styles.columnLabel}>
                {column.label}
              </div>
            ))}
            <div />
          </div>
          {rows.map((row, index) => (
            <div key={row.id} className={styles.row}>
              <div className={styles.grid}>
                {columns.map((column) => (
                  <div key={column.key}>{column.render(row, index)}</div>
                ))}
                {!locked ? (
                  <button
                    type="button"
                    onClick={() => onRemove(index)}
                    className={styles.rowRemove}
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
        <div className={styles.addRowWrap}>
          <button type="button" onClick={onAdd} className={styles.addRow}>
            {Ic.plus()} {category.addLabel}
          </button>
        </div>
      )}
    </Surface>
  );
}
