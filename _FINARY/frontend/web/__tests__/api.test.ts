import { describe, it, expect } from "vitest";
import { api } from "../lib/api";

describe("API client", () => {
  it("exports all endpoint functions", () => {
    expect(api.getNetWorth).toBeDefined();
    expect(api.getNetWorthHistory).toBeDefined();
    expect(api.getAccounts).toBeDefined();
    expect(api.getAccount).toBeDefined();
    expect(api.getAccountTransactions).toBeDefined();
    expect(api.getPortfolio).toBeDefined();
    expect(api.getPosition).toBeDefined();
    expect(api.getAllocation).toBeDefined();
    expect(api.getDividends).toBeDefined();
    expect(api.getTransactions).toBeDefined();
    expect(api.updateCategory).toBeDefined();
    expect(api.getMonthlyBudget).toBeDefined();
    expect(api.getCategorySpending).toBeDefined();
    expect(api.getQuote).toBeDefined();
    expect(api.getHistory).toBeDefined();
    expect(api.getFxRates).toBeDefined();
    expect(api.getDiversification).toBeDefined();
    expect(api.getAlerts).toBeDefined();
    expect(api.createAlert).toBeDefined();
    expect(api.deleteAlert).toBeDefined();
  });

  it("all functions are callable", () => {
    for (const [key, fn] of Object.entries(api)) {
      expect(typeof fn).toBe("function");
    }
  });
});
