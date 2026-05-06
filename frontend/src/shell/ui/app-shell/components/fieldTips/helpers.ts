export function descToTwoTierTips(desc: string): string[] {
  const text = (desc || "").trim();
  if (!text) return [];
  const firstSentenceEnd = text.indexOf(".");
  if (firstSentenceEnd === -1 || firstSentenceEnd === text.length - 1) return [text];
  const first = text.slice(0, firstSentenceEnd + 1).trim();
  const second = text.slice(firstSentenceEnd + 1).trim();
  return second ? [first, second] : [first];
}
