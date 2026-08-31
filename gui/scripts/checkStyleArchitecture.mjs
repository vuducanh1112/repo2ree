/* Style-architecture guard.
 *
 * The boundary is that CSS owns visual values, core owns identities, and a
 * `style` prop carries calculated custom properties or nothing. Biome and tsc
 * see none of that, so this is the only thing that does.
 *
 * The rules are absolute. There is no baseline file and no exceptions list:
 * during the migration this ran as a ratchet over a recorded inventory, and
 * that inventory reached zero and was deleted. A violation here is a violation,
 * wherever it is.
 *
 * TS/TSX rules run over the TypeScript AST rather than the file text, so
 * reformatting, nesting, or splitting an expression cannot hide a violation.
 */

import { readdirSync, readFileSync } from "node:fs";
import { dirname, extname, join, posix, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const guiRoot = fileURLToPath(new URL("..", import.meta.url));
const sourceRoot = join(guiRoot, "src");

// ================================================
// What counts as production source
// ================================================

const TEST_FILE = /[.](?:test|spec)[.]tsx?$/;
const GENERATED = "src/shell/infra/api/generated/";

/** Raw colors belong to the primitive/theme layers, or to a module that draws
 * an instrument: the milled metal, optical glass and readout inks a bay is
 * built from are artwork values, not semantic roles anything else consumes. */
const COLOR_VALUE_STYLESHEETS = new Set([
  "src/shell/ui/theme/tokens.css",
  "src/shell/ui/theme/light.css",
  "src/shell/ui/agents/LabCell.module.css",
  "src/shell/ui/app-shell/canvas/PodWidget.module.css",
  "src/shell/ui/app-shell/canvas/SpecimenPod.module.css",
  "src/shell/ui/app-shell/canvas/LabBackdrop.module.css",
  "src/shell/ui/app-shell/canvas/CanvasHub.module.css",
]);

/** Files that map low-level palette and material values to semantic roles. */
const LOW_LEVEL_THEME_STYLESHEETS = new Set([
  ...COLOR_VALUE_STYLESHEETS,
  "src/shell/ui/theme/tones.css",
]);

/** The modules the migration deleted. Naming them keeps the deletion from
 * being quietly undone by a re-introduced file of the same name. */
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
    "legacyGlobals",
  ].map((name) => `src/shell/ui/theme/${name}`),
);

// ================================================
// Rules
// ================================================

const RULES = {
  "raw-color": "raw color literal — move the value into a theme-owned stylesheet",
  "legacy-theme-import": "imports a legacy theme module — use CSS Modules and semantic roles",
  "style-object-literal": "literal style={{ ... }} — move the declarations into a CSS Module",
  "style-not-css-vars": "style prop not produced by cssVars() — pass calculated custom properties",
  "unowned-button":
    "intrinsic button has no visual owner — use Button or add an explicit CSS Module class",
  "alpha-interpolation": "alpha appended to a token — declare the translucent value in tokens.css",
  "theme-style-object": "theme module exports a style object — a CSS Module owns declarations",
  "core-visual-field": "visual field in core — expose the domain identity, not its presentation",
  "low-level-theme-reference":
    "low-level theme reference outside a theme mapping — consume a semantic or artwork role",
  "css-raw-color": "raw color outside a theme-owned stylesheet — consume a semantic role",
  "css-important": "!important outside the reduced-motion policy",
  "css-global-interaction":
    "global interaction selector — the component's module owns hover/active",
  "css-font-size-literal": "font-size outside the approved role-based type scale",
  "css-spacing-literal": "literal spacing — use the spacing scale",
  "css-radius-literal": "literal radius — use the radius scale",
  "css-font-weight-literal": "literal font weight — use the weight scale",
  "css-line-height-literal": "literal line-height — use the leading scale",
  "css-letter-spacing-literal": "literal letter-spacing — use the tracking scale",
  "css-opacity-literal": "fractional opacity — use the state opacity scale",
  "css-motion-duration-literal": "literal interaction duration — use the motion scale",
  "css-transition-all": "transition: all — name the properties that animate",
  "css-neutral-film-alpha": "neutral white film alpha outside the five-stop palette",
  "css-unused-theme-property":
    "theme custom property is unreachable from production CSS or TypeScript",
  "theme-component-recipe": "component-specific recipe declared in the global theme",
  "theme-alias-depth": "theme alias chain is deeper than two definitions",
};

const HEX_COLOR = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/;
const FUNCTIONAL_COLOR = /\b(?:rgb|rgba|hsl|hsla)\(/;
const LOW_LEVEL_THEME_REFERENCE = /var\(--palette-/;
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
      if (LOW_LEVEL_THEME_REFERENCE.test(node.text)) {
        at(node, "low-level-theme-reference", node.text.trim().slice(0, 60));
      }
    } else if (ts.isTemplateExpression(node)) {
      const chunks = [node.head, ...node.templateSpans.map((span) => span.literal)];
      if (chunks.some((chunk) => hasRawColor(chunk.text)))
        at(node, "raw-color", "template literal");
      if (chunks.some((chunk) => LOW_LEVEL_THEME_REFERENCE.test(chunk.text))) {
        at(node, "low-level-theme-reference", "template literal");
      }
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

    if (
      (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
      ts.isIdentifier(node.tagName) &&
      node.tagName.text === "button"
    ) {
      const hasExplicitClassName = node.attributes.properties.some(
        (attribute) =>
          ts.isJsxAttribute(attribute) && attribute.name.getText(source) === "className",
      );
      if (!hasExplicitClassName) {
        at(
          node,
          "unowned-button",
          "use the shared Button primitive or give this specialized control a className",
        );
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
const TYPE_TOKENS = "src/shell/ui/theme/tokens.css";
const LIGHT_THEME = "src/shell/ui/theme/light.css";
const TYPE_ROLES = new Set([
  "--text-micro",
  "--text-caption",
  "--text-label",
  "--text-body",
  "--text-body-large",
  "--text-heading-small",
  "--text-heading",
  "--text-heading-large",
  "--text-display",
]);
const NEUTRAL_FILM_STOPS = new Map([
  ["--surface-glass-subtle", "45"],
  ["--surface-raised", "62"],
  ["--surface-control", "72"],
  ["--surface-overlay", "85"],
  ["--surface-solid", "92"],
]);
const COMPONENT_RECIPE_PREFIX =
  /^--(?:app|control|download|field|footer|option|page|panel|section|switch|window|workspace)-/;
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

  if (!COLOR_VALUE_STYLESHEETS.has(file)) {
    for (const pattern of [new RegExp(HEX_COLOR, "g"), new RegExp(FUNCTIONAL_COLOR, "g")]) {
      for (const match of text.matchAll(pattern)) at(match.index, "css-raw-color", match[0]);
    }
  }

  if (!LOW_LEVEL_THEME_STYLESHEETS.has(file)) {
    const pattern = new RegExp(LOW_LEVEL_THEME_REFERENCE, "g");
    for (const match of text.matchAll(pattern)) {
      at(match.index, "low-level-theme-reference", match[0]);
    }
  }

  // Typography is a deliberately small, role-based scale. Calculated canvas
  // labels remain geometry, but every ordinary component must choose a text
  // role instead of introducing another optical near-duplicate.
  if (file === TYPE_TOKENS) {
    for (const match of text.matchAll(/(--text-[a-z-]+)\s*:/g)) {
      if (!TYPE_ROLES.has(match[1])) {
        at(match.index, "css-font-size-literal", match[1]);
      }
    }
  } else {
    for (const match of text.matchAll(/font-size\s*:\s*([^;}]+)/g)) {
      const value = match[1].trim();
      const role = value.match(/^var\((--text-[a-z-]+)\)$/)?.[1];
      if (!value.startsWith("calc(") && (!role || !TYPE_ROLES.has(role))) {
        at(match.index, "css-font-size-literal", value);
      }
    }
  }

  if (file !== TYPE_TOKENS) {
    const declarationRules = [
      [
        /(?:margin(?:-[a-z-]+)?|padding(?:-[a-z-]+)?|gap|row-gap|column-gap)\s*:[^;}]*[1-9][0-9.]*px/g,
        "css-spacing-literal",
      ],
      [/border-radius\s*:[^;}]*[0-9.]+px/g, "css-radius-literal"],
      [/font-weight\s*:\s*[0-9]+/g, "css-font-weight-literal"],
      [/line-height\s*:\s*[0-9.]+/g, "css-line-height-literal"],
      [/letter-spacing\s*:\s*-?[0-9.]+(?:px|em)/g, "css-letter-spacing-literal"],
      [/opacity\s*:\s*0\.[0-9]+/g, "css-opacity-literal"],
      [
        /(?:transition|animation)(?:-[a-z-]+)?\s*:[^;}]*\b0\.[0-9]+s/g,
        "css-motion-duration-literal",
      ],
      [/transition\s*:\s*all\b/g, "css-transition-all"],
    ];
    for (const [pattern, rule] of declarationRules) {
      for (const match of text.matchAll(pattern)) at(match.index, rule, match[0].trim());
    }
  }

  if (file.startsWith(THEME_ROOT)) {
    for (const match of text.matchAll(/^\s*(--[a-zA-Z0-9_-]+)\s*:/gm)) {
      if (COMPONENT_RECIPE_PREFIX.test(match[1])) {
        at(match.index, "theme-component-recipe", match[1]);
      }
    }
  }

  // Neutral glass has five perceptible opacity stops. Tinted films have their
  // own palettes; this guard addresses only white films in the light theme.
  if (file === LIGHT_THEME) {
    for (const match of text.matchAll(/rgb\(255 255 255 \/ ([0-9.]+)%\)/g)) {
      const lineStart = text.lastIndexOf("\n", match.index) + 1;
      const property = text.slice(lineStart, match.index).match(/^\s*(--[a-z0-9-]+)\s*:\s*$/)?.[1];
      const alpha = match[1];
      if (NEUTRAL_FILM_STOPS.get(property) !== alpha) {
        at(match.index, "css-neutral-film-alpha", `${property ?? "inline value"}: ${alpha}%`);
      }
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
// Theme custom-property reachability
// ================================================

const THEME_ROOT = "src/shell/ui/theme/";
const CUSTOM_PROPERTY_DEFINITION = /^\s*(--[a-zA-Z0-9_-]+)\s*:\s*([\s\S]*?);/gm;
const CUSTOM_PROPERTY_REFERENCE = /var\((--[a-zA-Z0-9_-]+)/g;
const DYNAMIC_TONE_REFERENCE =
  /^(?:--stage-.+-(?:line|ink|wash)|--axis-.+-(?:line|ink)|--eco-.+-(?:line|wash)|--dependency-.+-(?:line|wash|edge)|--archive-.+-(?:line|ink)|--failure-.+-line)$/;

/**
 * A theme property is live when production CSS/TS references it, or when a
 * live property references it. Dynamic tone helpers build a small, typed set
 * of names in appearance.ts, so those declared families are explicit roots.
 */
function checkThemePropertyReachability(paths) {
  const definitions = new Map();
  const dependencies = new Map();
  const roots = new Set();

  for (const path of paths) {
    const file = relativePath(path);
    if (file.startsWith(GENERATED) || TEST_FILE.test(file)) continue;
    const extension = extname(path);
    if (extension !== ".css" && extension !== ".ts" && extension !== ".tsx") continue;

    const raw = readFileSync(path, "utf8");
    const text = raw.replace(/\/\*[\s\S]*?\*\//g, (comment) => comment.replace(/[^\n]/g, " "));
    const isThemeCss = file.startsWith(THEME_ROOT) && extension === ".css";

    if (!isThemeCss) {
      for (const match of text.matchAll(CUSTOM_PROPERTY_REFERENCE)) roots.add(match[1]);
      continue;
    }

    const ranges = [];
    for (const match of text.matchAll(CUSTOM_PROPERTY_DEFINITION)) {
      const name = match[1];
      definitions.set(name, { file, path, index: match.index });
      dependencies.set(
        name,
        new Set([...match[2].matchAll(CUSTOM_PROPERTY_REFERENCE)].map((reference) => reference[1])),
      );
      ranges.push([match.index, match.index + match[0].length]);
    }

    for (const match of text.matchAll(CUSTOM_PROPERTY_REFERENCE)) {
      const insideDefinition = ranges.some(
        ([start, end]) => match.index >= start && match.index < end,
      );
      if (!insideDefinition) roots.add(match[1]);
    }
  }

  for (const name of definitions.keys()) {
    if (DYNAMIC_TONE_REFERENCE.test(name)) roots.add(name);
  }

  const reachable = new Set();
  const visit = (name) => {
    if (reachable.has(name)) return;
    reachable.add(name);
    for (const dependency of dependencies.get(name) ?? []) visit(dependency);
  };
  for (const root of roots) visit(root);

  for (const [name, definition] of definitions) {
    if (reachable.has(name)) continue;
    const source = readFileSync(definition.path, "utf8");
    const { line, character } = positionOf(source, definition.index);
    report(definition.file, line, character, "css-unused-theme-property", name);
  }

  const exactAliases = new Map();
  for (const [name, values] of dependencies) {
    if (values.size === 1) exactAliases.set(name, [...values][0]);
  }
  const aliasDepth = (name, seen = new Set()) => {
    if (!exactAliases.has(name)) return 0;
    if (seen.has(name)) return Number.POSITIVE_INFINITY;
    seen.add(name);
    return 1 + aliasDepth(exactAliases.get(name), seen);
  };
  for (const [name, definition] of definitions) {
    const depth = aliasDepth(name);
    if (depth <= 2) continue;
    const source = readFileSync(definition.path, "utf8");
    const { line, character } = positionOf(source, definition.index);
    report(definition.file, line, character, "theme-alias-depth", `${name}: ${depth}`);
  }
}

// ================================================
// Run
// ================================================

const productionPaths = walk(sourceRoot);
for (const path of productionPaths) {
  const file = relativePath(path);
  if (file.startsWith(GENERATED) || TEST_FILE.test(file)) continue;
  const extension = extname(path);
  if (extension === ".ts" || extension === ".tsx") checkTypeScript(path);
  else if (extension === ".css") checkCss(path);
}
checkThemePropertyReachability(productionPaths);

if (violations.length > 0) {
  const byFile = new Map();
  for (const violation of violations) {
    if (!byFile.has(violation.file)) byFile.set(violation.file, []);
    byFile.get(violation.file).push(violation);
  }
  const report = [...byFile.keys()]
    .sort()
    .map((file) =>
      byFile
        .get(file)
        .map(
          (site) =>
            `  ${site.file}:${site.line}:${site.column}  ${RULES[site.rule]}\n      ${site.detail}`,
        )
        .join("\n"),
    )
    .join("\n");
  console.error(`Style-architecture violations (${violations.length}):\n\n${report}\n`);
  process.exitCode = 1;
} else {
  console.log("Style architecture holds: no violations.");
}
