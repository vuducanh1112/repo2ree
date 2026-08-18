import AxeBuilder from "@axe-core/playwright";
import type { Page, TestInfo } from "@playwright/test";

type AxeScan = Awaited<ReturnType<AxeBuilder["analyze"]>>;
type ContrastFinding = AxeScan["violations"][number];

export async function expectPageToMeetContrast(
  page: Page,
  testInfo: TestInfo,
  root?: string,
): Promise<void> {
  const builder = new AxeBuilder({ page }).withRules(["color-contrast"]);
  if (root) builder.include(root);
  // Toggle contains no rendered text. Axe treats its decorative knob as text
  // contrast; non-text control contrast needs a separate WCAG 1.4.11 check.
  builder.exclude('[data-ui="toggle"]');
  const scan = await builder.analyze();

  if (scan.incomplete.length > 0) {
    await testInfo.attach("axe-contrast-incomplete.json", {
      body: Buffer.from(JSON.stringify(scan.incomplete, null, 2)),
      contentType: "application/json",
    });
  }

  if (scan.violations.length > 0) throw new Error(formatFindings(scan.violations));
}

function formatFindings(findings: ContrastFinding[]): string {
  if (findings.length === 0) return "The page meets automated WCAG contrast checks";

  const details = findings.flatMap((finding) =>
    finding.nodes.map((node) => {
      const target = node.target.join(" ");
      const explanation = node.failureSummary ?? node.any.map((check) => check.message).join("; ");
      return `- ${target}: ${explanation}`;
    }),
  );

  return ["Automated contrast scan found WCAG violations:", ...details].join("\n");
}
