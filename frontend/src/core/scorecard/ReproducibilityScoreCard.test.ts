import { describe, expect, it } from "vitest";
import { parseReproducibilityScoreCard } from "./ReproducibilityScoreCard";

const wireCard = {
  schemaVersion: 1,
  level: 3,
  levelCode: "R3",
  levelName: "Functional",
  sealed: false,
  categories: [
    {
      key: "source",
      label: "Source",
      rungs: [
        { key: "linked", label: "Linked", reached: true, detail: "https://example.org/r.git" },
        { key: "acquired", label: "Acquired", reached: true, detail: "" },
        { key: "archived", label: "SWH-archived", reached: true, detail: "swh:1:snp:0" },
        { key: "included", label: "Included", reached: false, detail: "" },
      ],
    },
    {
      key: "experiments",
      label: "Experiments",
      rungs: [{ key: "validated", label: "Validated", reached: false, done: 1, total: 3 }],
    },
  ],
};

describe("parseReproducibilityScoreCard", () => {
  it("parses a wire payload into the typed card", () => {
    const card = parseReproducibilityScoreCard(wireCard);
    expect(card).not.toBeNull();
    expect(card?.levelCode).toBe("R3");
    expect(card?.levelName).toBe("Functional");
    expect(card?.categories.map((category) => category.key)).toEqual(["source", "experiments"]);
    const validated = card?.categories[1].rungs[0];
    expect(validated).toMatchObject({ reached: false, done: 1, total: 3 });
    // Rungs without a fraction normalize to null, not undefined.
    expect(card?.categories[0].rungs[0].done).toBeNull();
  });

  it("rejects payloads without a numeric level", () => {
    expect(parseReproducibilityScoreCard({ categories: [] })).toBeNull();
    expect(parseReproducibilityScoreCard(null)).toBeNull();
    expect(parseReproducibilityScoreCard("R3")).toBeNull();
  });

  it("drops malformed categories and rungs instead of failing", () => {
    const card = parseReproducibilityScoreCard({
      level: 0,
      categories: [{ key: "bogus", label: "?" }, wireCard.categories[0], { rungs: [{}] }],
    });
    expect(card?.categories).toHaveLength(1);
    expect(card?.categories[0].key).toBe("source");
    // Missing levelCode falls back to the level.
    expect(card?.levelCode).toBe("R0");
  });
});
