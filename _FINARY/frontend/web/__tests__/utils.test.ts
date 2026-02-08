import { describe, it, expect } from "vitest";
import {
  formatEUR,
  formatCurrency,
  formatPct,
  formatNumber,
  pnlColor,
  CATEGORY_LABELS,
  CHART_COLORS,
} from "../lib/utils";

describe("formatEUR", () => {
  it("formats positive euros", () => {
    const result = formatEUR(12345.67);
    // fr-FR format: 12 345,67 €
    expect(result).toContain("12");
    expect(result).toContain("345");
    expect(result).toContain("67");
    expect(result).toContain("€");
  });

  it("formats negative euros", () => {
    const result = formatEUR(-1250.0);
    expect(result).toContain("1");
    expect(result).toContain("250");
    expect(result).toContain("€");
  });

  it("formats zero", () => {
    const result = formatEUR(0);
    expect(result).toContain("0");
    expect(result).toContain("€");
  });
});

describe("formatCurrency", () => {
  it("formats USD", () => {
    const result = formatCurrency(1000, "USD");
    expect(result).toContain("1");
    expect(result).toContain("000");
    expect(result).toContain("$");
  });

  it("formats GBP", () => {
    const result = formatCurrency(500, "GBP");
    expect(result).toContain("500");
    expect(result).toContain("£");
  });
});

describe("formatPct", () => {
  it("formats positive percentage with +", () => {
    expect(formatPct(12.34)).toBe("+12.34 %");
  });

  it("formats negative percentage", () => {
    expect(formatPct(-5.5)).toBe("-5.50 %");
  });

  it("formats zero", () => {
    expect(formatPct(0)).toBe("+0.00 %");
  });

  it("respects custom decimals", () => {
    expect(formatPct(12.345, 1)).toBe("+12.3 %");
  });
});

describe("formatNumber", () => {
  it("formats with thousand separator", () => {
    const result = formatNumber(12345.67);
    // fr-FR uses space as thousand sep and comma as decimal
    expect(result).toContain("12");
    expect(result).toContain("345");
  });
});

describe("pnlColor", () => {
  it("returns green for positive", () => {
    expect(pnlColor(100)).toBe("text-[#1fc090]");
  });

  it("returns red for negative", () => {
    expect(pnlColor(-50)).toBe("text-[#e54949]");
  });

  it("returns muted for zero", () => {
    expect(pnlColor(0)).toBe("text-[#6e727a]");
  });
});

describe("CATEGORY_LABELS", () => {
  it("has French labels for common categories", () => {
    expect(CATEGORY_LABELS.alimentation).toBe("Alimentation");
    expect(CATEGORY_LABELS.logement).toBe("Logement");
    expect(CATEGORY_LABELS.revenus).toBe("Revenus");
    expect(CATEGORY_LABELS.sante).toBe("Santé");
  });
});

describe("CHART_COLORS", () => {
  it("has at least 10 colors", () => {
    expect(CHART_COLORS.length).toBeGreaterThanOrEqual(10);
  });

  it("colors are hex format", () => {
    for (const color of CHART_COLORS) {
      expect(color).toMatch(/^#[0-9a-f]{6}$/);
    }
  });
});
