import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import ts from "typescript";

const KEPT = [
  /eslint-(disable|enable)/,
  /@ts-(expect-error|ignore|nocheck|check)/,
  /^\/\/\/\s*<reference/,
  /biome-ignore/,
  /@vitest-environment/,
  /(istanbul|c8|v8) ignore/,
  /[#@]__PURE__/,
  /@vite-ignore/,
];
const TYPED = /@(type|typedef|satisfies|import|template|callback)\b|@(param|returns?)\s*\{/;
const SCRIPT = /\.(ts|tsx|mts|cts|js|mjs|cjs)$/;
const GENERATED = /(^|\/)generated\//;

function kindOf(file) {
  if (file.endsWith(".tsx")) return ts.ScriptKind.TSX;
  if (/\.(ts|mts|cts)$/.test(file)) return ts.ScriptKind.TS;
  return ts.ScriptKind.JS;
}

function scriptComments(file, text) {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kindOf(file));
  const found = new Map();
  const jsxText = [];
  const emptyJsx = [];
  const add = (ranges) => {
    for (const range of ranges ?? []) found.set(range.pos, range.end);
  };
  const visit = (node) => {
    if (node.kind === ts.SyntaxKind.JsxText) {
      jsxText.push([node.pos, node.end]);
      return;
    }
    if (node.kind === ts.SyntaxKind.JsxExpression && !node.expression) {
      emptyJsx.push([node.getStart(source), node.end]);
    }
    add(ts.getLeadingCommentRanges(text, node.getFullStart()));
    add(ts.getTrailingCommentRanges(text, node.getEnd()));
    for (const child of node.getChildren(source)) visit(child);
  };
  visit(source);
  const within = (pos, end, spans) => spans.some(([start, stop]) => pos >= start && pos < stop);
  let cuts = [...found]
    .filter(([pos]) => !(pos === 0 && text.startsWith("#!")))
    .filter(([pos, end]) => !within(pos, end, jsxText))
    .filter(([pos, end]) => !KEPT.some((pattern) => pattern.test(text.slice(pos, end))))
    .filter(([pos, end]) => kindOf(file) !== ts.ScriptKind.JS || !TYPED.test(text.slice(pos, end)));
  for (const [start, stop] of emptyJsx) {
    const inner = cuts.filter(([pos, end]) => pos >= start && end <= stop);
    let rest = text.slice(start + 1, stop - 1);
    for (const [pos, end] of inner) rest = rest.replace(text.slice(pos, end), "");
    if (rest.trim() === "") {
      cuts = cuts.filter(([pos, end]) => !(pos >= start && end <= stop));
      cuts.push([start, stop]);
    }
  }
  return cuts;
}

function styleComments(text) {
  return [...text.matchAll(/\/\*[\s\S]*?\*\//g)]
    .filter((match) => !KEPT.some((pattern) => pattern.test(match[0])))
    .map((match) => [match.index, match.index + match[0].length]);
}

function without(text, cuts) {
  let out = text;
  for (const [pos, end] of [...cuts].sort((a, b) => b[0] - a[0])) {
    const lineStart = out.lastIndexOf("\n", pos - 1) + 1;
    const found = out.indexOf("\n", end);
    const lineEnd = found === -1 ? out.length : found;
    const before = out.slice(lineStart, pos);
    const after = out.slice(end, lineEnd);
    if (before.trim() === "" && after.trim() === "") {
      out = out.slice(0, lineStart) + out.slice(Math.min(lineEnd + 1, out.length));
      continue;
    }
    let start = pos;
    while (start > lineStart && (out[start - 1] === " " || out[start - 1] === "\t")) start--;
    const tail = out.slice(end).replace(/^[ \t]+/, "");
    out = out.slice(0, start) + (after.trim() === "" ? "" : " ") + tail;
  }
  return out;
}

function stripped(file, text) {
  const cuts = file.endsWith(".css") ? styleComments(text) : scriptComments(file, text);
  return cuts.length === 0 ? text : without(text, cuts);
}

function tracked() {
  return execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard"], {
    encoding: "utf8",
  })
    .split("\n")
    .filter((file) => (SCRIPT.test(file) || file.endsWith(".css")) && !GENERATED.test(file))
    .filter((file) => !file.startsWith("node_modules/") && !file.startsWith("dist/"));
}

const fix = process.argv.includes("--fix");
const named = process.argv.slice(2).filter((arg) => arg !== "--fix");
const commented = [];
for (const file of named.length > 0 ? named : tracked()) {
  const text = readFileSync(file, "utf8");
  const result = stripped(file, text);
  if (result === text) continue;
  if (fix) writeFileSync(file, result);
  else commented.push(file);
}
for (const file of commented) console.error(`${file}: comments`);
if (commented.length > 0) {
  console.error("just fix-no-code-comments removes them; just format tidies what is left");
  process.exit(1);
}
