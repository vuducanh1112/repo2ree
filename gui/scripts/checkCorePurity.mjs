import { readdirSync, readFileSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const coreRoot = fileURLToPath(new URL("../src/core", import.meta.url));
const sourceExtensions = new Set([".ts", ".tsx"]);
const ambientIdentifiers = new Set([
  "cancelAnimationFrame",
  "crypto",
  "document",
  "fetch",
  "FileReader",
  "localStorage",
  "navigator",
  "requestAnimationFrame",
  "sessionStorage",
  "setInterval",
  "setTimeout",
  "WebSocket",
  "window",
  "XMLHttpRequest",
]);

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    if (!sourceExtensions.has(extname(entry.name)) || /[.](?:test|spec)[.]tsx?$/.test(entry.name)) {
      return [];
    }
    return [path];
  });
}

function propertyCall(node, owner, member) {
  return (
    ts.isCallExpression(node) &&
    ts.isPropertyAccessExpression(node.expression) &&
    ts.isIdentifier(node.expression.expression) &&
    node.expression.expression.text === owner &&
    node.expression.name.text === member
  );
}

const violations = [];
for (const path of sourceFiles(coreRoot)) {
  const text = readFileSync(path, "utf8");
  const source = ts.createSourceFile(
    path,
    text,
    ts.ScriptTarget.Latest,
    true,
    path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );

  function report(node, effect) {
    const { line, character } = source.getLineAndCharacterOfPosition(node.getStart(source));
    violations.push(`${path}:${line + 1}:${character + 1}: ${effect}`);
  }

  function visit(node) {
    if (
      ts.isNewExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "Date" &&
      (node.arguments?.length ?? 0) === 0
    ) {
      report(node, "read the clock through an injected port instead of new Date()");
    } else if (propertyCall(node, "Date", "now")) {
      report(node, "read the clock through an injected port instead of Date.now()");
    } else if (propertyCall(node, "Math", "random")) {
      report(node, "obtain randomness through an injected port instead of Math.random()");
    } else if (
      ts.isIdentifier(node) &&
      ambientIdentifiers.has(node.text) &&
      !(ts.isPropertyAccessExpression(node.parent) && node.parent.name === node)
    ) {
      report(node, `imperative global ${node.text} is not allowed in the functional core`);
    }
    ts.forEachChild(node, visit);
  }

  visit(source);
}

if (violations.length > 0) {
  console.error(`Functional-core effect violations:\n${violations.join("\n")}`);
  process.exitCode = 1;
} else {
  console.log(
    "Functional core has no ambient clock, randomness, browser, timer, or network effects.",
  );
}
