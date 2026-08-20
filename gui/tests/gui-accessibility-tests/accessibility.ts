import AxeBuilder from "@axe-core/playwright";
import type { Page, TestInfo } from "@playwright/test";

const ACCESSIBILITY_TAGS = [
  "wcag2a",
  "wcag2aa",
  "wcag21a",
  "wcag21aa",
  "wcag22aa",
  "best-practice",
];

type AxeScan = Awaited<ReturnType<AxeBuilder["analyze"]>>;
type AxeFinding = AxeScan["violations"][number];

export async function expectPageToMeetAccessibilityStandards(
  page: Page,
  testInfo: TestInfo,
): Promise<void> {
  const scan = await new AxeBuilder({ page }).withTags(ACCESSIBILITY_TAGS).analyze();

  await testInfo.attach("axe-accessibility-findings.json", {
    body: Buffer.from(
      JSON.stringify({ violations: scan.violations, incomplete: scan.incomplete }, null, 2),
    ),
    contentType: "application/json",
  });

  if (scan.violations.length > 0) throw new Error(formatFindings(scan.violations));
}

function formatFindings(findings: AxeFinding[]): string {
  const details = findings.flatMap((finding) => [
    `${finding.id} (${finding.impact ?? "unknown impact"}): ${finding.help}`,
    ...finding.nodes.map((node) => {
      const target = node.target.join(" ");
      const explanation = node.failureSummary ?? node.any.map((check) => check.message).join("; ");
      return `- ${target}: ${explanation}`;
    }),
  ]);

  return ["Automated accessibility scan found violations:", ...details].join("\n");
}
