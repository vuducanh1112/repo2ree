import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const read = (relativePath: string): string =>
  readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");

describe("font assets", () => {
  it.each([
    {
      family: "Inter Variable",
      packageCss: "../../../../node_modules/@fontsource-variable/inter/wght.css",
      packageImport: "@fontsource-variable/inter/wght.css",
      token: "--font-sans",
    },
    {
      family: "JetBrains Mono Variable",
      packageCss: "../../../../node_modules/@fontsource-variable/jetbrains-mono/wght.css",
      packageImport: "@fontsource-variable/jetbrains-mono/wght.css",
      token: "--font-mono",
    },
  ])("ships and selects $family", ({ family, packageCss, packageImport, token }) => {
    const bootstrap = read("../../app/bootstrap/AppBootstrap.tsx");
    const tokens = read("./tokens.css");
    const fontFaces = read(packageCss);

    expect(bootstrap).toContain(`import "${packageImport}";`);
    expect(tokens).toMatch(new RegExp(`${token}:[^;]*"${family}"`));
    expect(fontFaces).toContain(`font-family: '${family}'`);
    expect(fontFaces).toContain("font-display: swap");
    expect(fontFaces).toContain("format('woff2-variations')");
  });
});
