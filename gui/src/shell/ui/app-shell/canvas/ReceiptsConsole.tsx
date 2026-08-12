import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import { useAuthorReceiptsQuery } from "@shell/data/receipts/queries";
import { type ReactNode, useMemo, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { HudConsole } from "./HudConsole";
import hud from "./HudConsole.module.css";
import { ReceiptCard } from "./ReceiptCard";
import styles from "./ReceiptsConsole.module.css";

const HUD_WIDTH_OPEN = 380;
const HUD_WIDTH_COLLAPSED = 224;

interface ReceiptsConsoleProps {
  provisioned: boolean;
}

// The receipts console — the upper-right HUD, and the one place the REE's
// materialised evidence lives. Today it holds the author receipts the backend
// keeps under `receipts/author`; review receipts (and the diffs they carry)
// become a second section of the same console, which is why the body is built
// from titled sections rather than a single flat list.
export function ReceiptsConsole({ provisioned }: ReceiptsConsoleProps) {
  const [open, setOpen] = useState(false);
  const query = useAuthorReceiptsQuery({ enabled: provisioned });
  const receipts = useMemo(() => parseAuthorReceipts(query.data), [query.data]);

  const subtitle = !provisioned
    ? "awaiting workbench"
    : receipts.length === 0
      ? "no evidence recorded"
      : `${receipts.length} receipt${receipts.length === 1 ? "" : "s"}`;

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={HUD_WIDTH_OPEN}
      widthCollapsed={HUD_WIDTH_COLLAPSED}
      className={hud.receiptsPlacement}
      icon={Ic.shield(16)}
      iconTint={receipts.length > 0 ? "var(--chrome-accent)" : undefined}
      title="Receipts"
      subtitle={subtitle}
      on={receipts.length > 0}
      expandLabel="Expand receipts"
      collapseLabel="Collapse receipts"
      bodyMaxHeight={560}
      bodyClassName={hud.receiptsBody}
    >
      <Section title="Author evidence">
        {query.isError ? (
          <Empty>Receipts unavailable.</Empty>
        ) : receipts.length === 0 ? (
          <Empty>No author receipts recorded yet.</Empty>
        ) : (
          receipts.map((receipt) => <ReceiptCard key={receipt.key} receipt={receipt} />)
        )}
      </Section>
    </HudConsole>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div className={styles.empty}>{children}</div>;
}
