import { describe, it, expect } from "vitest";
import { calculateTotalCost, formatCurrency } from "./formatting";

describe("formatCurrency", () => {
  it("formats a whole number with two decimals", () => {
    expect(formatCurrency(1234)).toBe("£1,234.00");
  });

  it("formats a number with decimals", () => {
    expect(formatCurrency(1234.56)).toBe("£1,234.56");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("£0.00");
  });
});

describe("calculateTotalCost", () => {
  it("sums numeric cost-if-not-fixed values", () => {
    const actions = [
      { costIfNotFixed: "approximately £1,234.56 in the next 4 weeks" },
      { costIfNotFixed: "£500 in unnecessary overrides" },
    ];
    expect(calculateTotalCost(actions)).toBe(1734.56);
  });

  it("ignores narrative-only entries", () => {
    const actions = [
      {
        costIfNotFixed:
          "If compliance continues to fall, straight-to-bin waste is likely to increase.",
      },
      { costIfNotFixed: "£100" },
    ];
    expect(calculateTotalCost(actions)).toBe(100);
  });

  it("handles missing costIfNotFixed", () => {
    const actions = [
      { costIfNotFixed: "£1,000" },
      {},
      { costIfNotFixed: undefined },
    ];
    expect(calculateTotalCost(actions)).toBe(1000);
  });

  it("returns zero for an empty list", () => {
    expect(calculateTotalCost([])).toBe(0);
  });

  it("handles multiple comma-separated values", () => {
    const actions = [
      { costIfNotFixed: "£1,000,000" },
      { costIfNotFixed: "£2,500.50" },
    ];
    expect(calculateTotalCost(actions)).toBe(1002500.5);
  });
});
