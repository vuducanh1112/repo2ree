import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import { useAuthorReceiptsQuery } from "@shell/data/receipts/queries";
import { type ReactNode, useMemo, useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { lgColors } from "../../theme/lightGlassTheme";
import { C, F } from "../../theme/theme";
import { HudConsole } from "./HudConsole";
import { ReceiptCard } from "./ReceiptCard";

const HUD_RIGHT = 16;
const HUD_TOP = 16;
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

  const staleCount = receipts.filter((receipt) => receipt.freshness !== "fresh").length;
  const subtitle = !provisioned
    ? "awaiting workbench"
    : receipts.length === 0
      ? "no evidence recorded"
      : `${receipts.length} receipt${receipts.length === 1 ? "" : "s"}${
          staleCount > 0 ? ` · ${staleCount} stale` : ""
        }`;

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={HUD_WIDTH_OPEN}
      widthCollapsed={HUD_WIDTH_COLLAPSED}
      outerStyle={{ right: HUD_RIGHT, top: HUD_TOP, maxHeight: "calc(100% - 32px)" }}
      icon={Ic.shield(16)}
      iconColor={receipts.length > 0 ? C.accent : lgColors.textMuted}
      title="Receipts"
      subtitle={subtitle}
      on={receipts.length > 0}
      expandLabel="Expand receipts"
      collapseLabel="Collapse receipts"
      bodyMaxHeight={560}
      bodyStyle={{ gap: 9, overflowY: "auto" }}
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
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div
        style={{
          color: C.textMid,
          fontSize: 10,
          fontWeight: 800,
          fontFamily: F.mono,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div style={{ color: C.textMuted, fontSize: 10.5 }}>{children}</div>;
}
