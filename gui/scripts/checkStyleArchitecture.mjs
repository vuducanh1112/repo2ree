/* Style-architecture guard.
 *
 * The rework's boundary is that CSS owns visual values, core owns identities,
 * and a `style` prop carries calculated custom properties or nothing. Biome and
 * tsc see neither of those, so this is the only thing that does.
 *
 * It runs as a ratchet while the migration is in flight: every violation that
 * exists today is recorded in `styleArchitectureInventory.json`, and the check
 * fails both when a file gains a violation *and* when it loses one without the
 * inventory being updated. A ratchet that only counts up lets debt sit; one
 * that also fails on stale entries makes each phase's shrinkage show up in the
 * diff. Regenerate with `--update` after a conversion.
 *
 * The inventory is a migration mechanism, not an accepted boundary. Phase 8
 * deletes it and the rules below become absolute.
 *
 * TS/TSX rules run over the TypeScript AST rather than the file text, so
 * reformatting, nesting, or splitting an expression cannot hide a violation.
 */

import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, join, posix, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const guiRoot = fileURLToPath(new URL("..", import.meta.url));
const sourceRoot = join(guiRoot, "src");
const inventoryPath = join(guiRoot, "scripts", "styleArchitectureInventory.json");
const update = process.argv.includes("--update");

// ================================================
// What counts as production source
// ================================================

const TEST_FILE = /[.](?:test|spec)[.]tsx?$/;
const GENERATED = "src/shell/infra/api/generated/";

/** The stylesheet that owns the raw palette; every other one consumes roles. */
const TOKENS_STYLESHEET = "src/shell/ui/theme/tokens.css";

const LEGACY_THEME_MODULES = new Set(
  [
    "globalCss",
    "tokens",
    "theme",
    "styles",
    "stylesCore",
    "stylesLayout",
    "lightGlassTheme",
    "hover",
  ].map((name) => `src/shell/ui/theme/${name}`),
);

// ================================================
// Rules
// ================================================

const RULES = {
  "raw-color": "raw color literal — move the value into theme/tokens.css",
  "legacy-theme-import": "imports a legacy theme module — use CSS Modules and semantic roles",
  "style-object-literal": "literal style={{ ... }} — move the declarations into a CSS Module",
  "style-not-css-vars": "style prop not produced by cssVars() — pass calculated custom properties",
  "alpha-interpolation": "alpha appended to a token — declare the translucent value in tokens.css",
  "theme-style-object": "theme module exports a style object — a CSS Module owns declarations",
  "core-visual-field": "visual field in core — expose the domain identity, not its presentation",
  "css-raw-color": "raw color outside theme/tokens.css — consume a semantic role",
  "css-important": "!important outside the reduced-motion policy",
  "css-global-interaction":
    "global interaction selector — the component's module owns hover/active",
};

const HEX_COLOR = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/;
const FUNCTIONAL_COLOR = /\b(?:rgb|rgba|hsl|hsla)\(/;
/** `${token}88` — an alpha suffix glued onto an interpolated value. */
const ALPHA_SUFFIX = /^[0-9a-fA-F]{2}(?![0-9a-zA-Z])/;

const hasRawColor = (text) => HEX_COLOR.test(text) || FUNCTIONAL_COLOR.test(text);

/** Property names that describe skin rather than domain or geometry. */
const VISUAL_FIELDS = new Set([
  "background",
  "backgroundColor",
  "backgroundImage",
  "border",
  "borderColor",
  "boxShadow",
  "color",
  "colors",
  "fill",
  "gradient",
  "palette",
  "shadow",
  "stroke",
  "swatch",
  "textColor",
  "tint",
]);

/** Enough CSS property names to recognise a style object without guessing. */
const CSS_PROPERTIES = new Set([
  "alignItems",
  "background",
  "backgroundColor",
  "border",
  "borderRadius",
  "boxShadow",
  "color",
  "display",
  "flex",
  "flexDirection",
  "fontFamily",
  "fontSize",
  "fontWeight",
  "gap",
  "gridTemplateColumns",
  "height",
  "justifyContent",
  "letterSpacing",
  "lineHeight",
  "margin",
  "opacity",
  "overflow",
  "padding",
  "position",
  "textAlign",
  "textTransform",
  "transition",
  "width",
  "zIndex",
]);

// ================================================
// Collection
// ================================================

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

const relativePath = (path) => relative(guiRoot, path).split("\\").join("/");

const violations = [];

function report(path, line, character, rule, detail) {
  violations.push({ file: path, line: line + 1, column: character + 1, rule, detail });
}

/** Resolve an import specifier to a repo-relative, extensionless module path. */
function resolveSpecifier(fromFile, specifier) {
  if (specifier.startsWith("@shell/")) return `src/shell/${specifier.slice(7)}`;
  if (specifier.startsWith("@core/")) return `src/core/${specifier.slice(6)}`;
  if (!specifier.startsWith(".")) return null;
  const resolved = relativePath(resolve(dirname(fromFile), specifier));
  return posix.normalize(resolved).replace(/[.](?:tsx?|jsx?)$/, "");
}

function checkTypeScript(path) {
  const file = relativePath(path);
  const text = readFileSync(path, "utf8");
  const source = ts.createSourceFile(
    path,
    text,
    ts.ScriptTarget.Latest,
    true,
    path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const inCore = file.startsWith("src/core/");
  const inTheme = file.startsWith("src/shell/ui/theme/");

  const at = (node, rule, detail) => {
    const { line, character } = source.getLineAndCharacterOfPosition(node.getStart(source));
    report(file, line, character, rule, detail);
  };

  /** Every property name written anywhere inside a node. */
  function propertyNames(node, names = []) {
    if (
      (ts.isPropertyAssignment(node) ||
        ts.isPropertySignature(node) ||
        ts.isShorthandPropertyAssignment(node)) &&
      (ts.isIdentifier(node.name) || ts.isStringLiteral(node.name))
    ) {
      names.push(node.name.text);
    }
    ts.forEachChild(node, (child) => propertyNames(child, names));
    return names;
  }

  function visit(node) {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      if (hasRawColor(node.text)) at(node, "raw-color", node.text.trim().slice(0, 60));
    } else if (ts.isTemplateExpression(node)) {
      const chunks = [node.head, ...node.templateSpans.map((span) => span.literal)];
      if (chunks.some((chunk) => hasRawColor(chunk.text)))
        at(node, "raw-color", "template literal");
      for (const span of node.templateSpans) {
        if (ALPHA_SUFFIX.test(span.literal.text)) {
          at(span, "alpha-interpolation", `\${…}${span.literal.text.slice(0, 4)}`);
        }
      }
    }

    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const target = resolveSpecifier(path, node.moduleSpecifier.text);
      if (target !== null && LEGACY_THEME_MODULES.has(target)) {
        at(node, "legacy-theme-import", node.moduleSpecifier.text);
      }
    }

    if (ts.isJsxAttribute(node) && node.name.getText(source) === "style" && node.initializer) {
      const expression = ts.isJsxExpression(node.initializer)
        ? node.initializer.expression
        : undefined;
      if (expression === undefined) {
        // `style="…"` — a string, never valid here.
        at(node, "style-not-css-vars", "string literal");
      } else if (ts.isObjectLiteralExpression(expression)) {
        at(node, "style-object-literal", "inline declarations");
      } else {
        const call = ts.isAsExpression(expression) ? expression.expression : expression;
        const producedByCssVars =
          ts.isCallExpression(call) &&
          ts.isIdentifier(call.expression) &&
          call.expression.text === "cssVars";
        if (!producedByCssVars) at(node, "style-not-css-vars", call.getText(source).slice(0, 60));
      }
    }

    if (inCore && (ts.isPropertyAssignment(node) || ts.isPropertySignature(node))) {
      const name =
        ts.isIdentifier(node.name) || ts.isStringLiteral(node.name) ? node.name.text : "";
      if (VISUAL_FIELDS.has(name)) at(node, "core-visual-field", name);
    }

    if (inTheme && ts.isVariableStatement(node) && isExported(node)) {
      for (const declaration of node.declarationList.declarations) {
        if (isStyleObject(declaration)) {
          at(declaration, "theme-style-object", declaration.name.getText(source));
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  const isExported = (node) =>
    node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword) ?? false;

  function isStyleObject(declaration) {
    const annotation = declaration.type?.getText(source) ?? "";
    if (annotation.includes("CSSProperties")) return true;
    if (declaration.initializer === undefined) return false;
    return propertyNames(declaration.initializer).some((name) => CSS_PROPERTIES.has(name));
  }

  visit(source);
}

// ================================================
// CSS
// ================================================

/** Selectors that reach every button or link in the app rather than one
 * component's. Scrollbar pseudo-elements are the documented exception: the
 * scrollbar has no component to own it. */
const INTERACTION_PSEUDO = /:(?:hover|active)\b/;
const SCROLLBAR = /::-webkit-scrollbar/;
const REDUCED_MOTION = /@media[^{]*prefers-reduced-motion[^{]*\{/g;

function positionOf(text, index) {
  const before = text.slice(0, index);
  const line = before.split("\n").length - 1;
  return { line, character: index - (before.lastIndexOf("\n") + 1) };
}

/** Brace-matched ranges of every reduced-motion block, where !important is the
 * whole point rather than a smell. */
function reducedMotionRanges(text) {
  const ranges = [];
  for (const match of text.matchAll(REDUCED_MOTION)) {
    let depth = 0;
    for (let index = match.index + match[0].length - 1; index < text.length; index += 1) {
      if (text[index] === "{") depth += 1;
      else if (text[index] === "}") {
        depth -= 1;
        if (depth === 0) {
          ranges.push([match.index, index]);
          break;
        }
      }
    }
  }
  return ranges;
}

function checkCss(path) {
  const file = relativePath(path);
  const raw = readFileSync(path, "utf8");
  // Blank comments rather than drop them, so offsets stay true to the file.
  const text = raw.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
  const isModule = file.endsWith(".module.css");

  const at = (index, rule, detail) => {
    const { line, character } = positionOf(text, index);
    report(file, line, character, rule, detail);
  };

  if (file !== TOKENS_STYLESHEET) {
    for (const pattern of [new RegExp(HEX_COLOR, "g"), new RegExp(FUNCTIONAL_COLOR, "g")]) {
      for (const match of text.matchAll(pattern)) at(match.index, "css-raw-color", match[0]);
    }
  }

  const exempt = reducedMotionRanges(text);
  for (const match of text.matchAll(/!important/g)) {
    const inside = exempt.some(([start, end]) => match.index > start && match.index < end);
    if (!inside) at(match.index, "css-important", "!important");
  }

  if (!isModule) {
    for (const match of text.matchAll(/(^|[};])\s*([^{};@]+)\{/g)) {
      const selector = match[2];
      if (INTERACTION_PSEUDO.test(selector) && !SCROLLBAR.test(selector)) {
        at(match.index + match[0].indexOf(selector), "css-global-interaction", selector.trim());
      }
    }
  }
}

// ================================================
// Run
// ================================================

for (const path of walk(sourceRoot)) {
  const file = relativePath(path);
  if (file.startsWith(GENERATED) || TEST_FILE.test(file)) continue;
  const extension = extname(path);
  if (extension === ".ts" || extension === ".tsx") checkTypeScript(path);
  else if (extension === ".css") checkCss(path);
}

/** file -> rule -> count */
function tally(entries) {
  const counts = {};
  for (const violation of entries) {
    counts[violation.file] ??= {};
    counts[violation.file][violation.rule] = (counts[violation.file][violation.rule] ?? 0) + 1;
  }
  return Object.fromEntries(
    Object.keys(counts)
      .sort()
      .map((file) => [
        file,
        Object.fromEntries(
          Object.keys(counts[file])
            .sort()
            .map((rule) => [rule, counts[file][rule]]),
        ),
      ]),
  );
}

const found = tally(violations);
const total = violations.length;

if (update) {
  const inventory = {
    note:
      "Migration ratchet for the GUI styling rework — pre-existing violations, per file. " +
      "It may only shrink: `make gui-checks` fails on a new violation and on a stale entry " +
      "left behind by a conversion. Regenerate with `npm run check:style-architecture -- --update`. " +
      "Phase 8 deletes this file and the rules become absolute.",
    total,
    files: found,
  };
  writeFileSync(inventoryPath, `${JSON.stringify(inventory, null, 2)}\n`);
  console.log(`Recorded ${total} style-architecture violations in ${relativePath(inventoryPath)}.`);
  process.exit(0);
}

const recorded = JSON.parse(readFileSync(inventoryPath, "utf8")).files;
const failures = [];

for (const [file, rules] of Object.entries(found)) {
  for (const [rule, count] of Object.entries(rules)) {
    const allowed = recorded[file]?.[rule] ?? 0;
    if (count > allowed) {
      const sites = violations.filter((entry) => entry.file === file && entry.rule === rule);
      failures.push(
        `${file}: ${count - allowed} new ${rule} violation(s) (recorded ${allowed}) — ${RULES[rule]}\n` +
          sites
            .slice(allowed)
            .map((site) => `    ${site.file}:${site.line}:${site.column}  ${site.detail}`)
            .join("\n"),
      );
    }
  }
}

for (const [file, rules] of Object.entries(recorded)) {
  for (const [rule, allowed] of Object.entries(rules)) {
    const count = found[file]?.[rule] ?? 0;
    if (count < allowed) {
      failures.push(
        `${file}: ${rule} is down to ${count} from a recorded ${allowed} — the ratchet has to ` +
          "record it: npm run check:style-architecture -- --update",
      );
    }
  }
}

if (failures.length > 0) {
  console.error(`Style-architecture violations:\n\n${failures.join("\n\n")}\n`);
  process.exitCode = 1;
} else {
  console.log(
    `Style architecture holds: ${total} recorded violation(s) across ${Object.keys(found).length} ` +
      "file(s), none new.",
  );
}
