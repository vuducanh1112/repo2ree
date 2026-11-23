import { readFileSync } from "node:fs";
import ts from "typescript";

const NAME = /^[a-z][a-z0-9_]*$/;

function declarationName(node) {
  for (let current = node; current; current = current.parent) {
    if (
      (ts.isVariableDeclaration(current) ||
        ts.isTypeAliasDeclaration(current) ||
        ts.isInterfaceDeclaration(current) ||
        ts.isFunctionDeclaration(current) ||
        ts.isClassDeclaration(current)) &&
      current.name &&
      ts.isIdentifier(current.name)
    ) {
      return current.name.text;
    }
  }
  return "<module>";
}

function keyName(name) {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name)) return name.text;
  return undefined;
}

function allNames(texts) {
  return texts.length >= 2 && texts.every((text) => text !== undefined && NAME.test(text))
    ? texts
    : undefined;
}

function stringLiteralType(type) {
  return ts.isLiteralTypeNode(type) && ts.isStringLiteral(type.literal)
    ? type.literal.text
    : undefined;
}

function setsOf(node) {
  if (ts.isArrayLiteralExpression(node)) {
    return [
      allNames(
        node.elements.map((element) => (ts.isStringLiteral(element) ? element.text : undefined)),
      ),
    ];
  }
  if (ts.isUnionTypeNode(node)) {
    return [allNames(node.types.map(stringLiteralType))];
  }
  if (ts.isObjectLiteralExpression(node)) {
    const assigned = node.properties.filter(ts.isPropertyAssignment);
    const keys = assigned
      .map((property) => keyName(property.name))
      .filter((key) => key && NAME.test(key));
    const values = assigned.map((property) =>
      ts.isStringLiteral(property.initializer) ? property.initializer.text : undefined,
    );
    return [
      keys.length >= 2 ? keys : undefined,
      assigned.length === node.properties.length ? allNames(values) : undefined,
    ];
  }
  if (ts.isInterfaceDeclaration(node) || ts.isTypeLiteralNode(node)) {
    const keys = node.members
      .filter(ts.isPropertySignature)
      .map((member) => keyName(member.name))
      .filter((key) => key && NAME.test(key));
    return [keys.length >= 2 ? keys : undefined];
  }
  return [];
}

function sitesOf(path) {
  const text = readFileSync(path, "utf8");
  const source = ts.createSourceFile(
    path,
    text,
    ts.ScriptTarget.Latest,
    true,
    path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const sites = [];
  const visit = (node) => {
    for (const names of setsOf(node)) {
      if (names) {
        sites.push({
          path,
          declaration: declarationName(node),
          start: node.getStart(source),
          names,
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return sites;
}

process.stdout.write(`${JSON.stringify(process.argv.slice(2).flatMap(sitesOf))}\n`);
