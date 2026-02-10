const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ─── Net Worth ───
export const api = {
  getNetWorth: () =>
    fetchApi<import("./types/api").NetWorthSummary>("/api/v1/networth"),
  getNetWorthHistory: (limit = 365) =>
    fetchApi<import("./types/api").NetWorthHistory[]>(
      `/api/v1/networth/history?limit=${limit}`
    ),

  // ─── Accounts ───
  getAccounts: () =>
    fetchApi<import("./types/api").Account[]>("/api/v1/accounts"),
  getAccount: (id: string) =>
    fetchApi<import("./types/api").Account>(`/api/v1/accounts/${id}`),
  getAccountTransactions: (id: string, limit = 50) =>
    fetchApi<import("./types/api").Transaction[]>(
      `/api/v1/accounts/${id}/transactions?limit=${limit}`
    ),

  // ─── Portfolio ───
  getPortfolio: () =>
    fetchApi<import("./types/api").PositionValuation[]>("/api/v1/portfolio"),
  getPosition: (id: string) =>
    fetchApi<import("./types/api").Position>(`/api/v1/positions/${id}`),
  getAllocation: () =>
    fetchApi<import("./types/api").Allocation>("/api/v1/portfolio/allocation"),
  getDividends: () =>
    fetchApi<import("./types/api").Dividend[]>("/api/v1/portfolio/dividends"),

  // ─── Transactions ───
  getTransactions: (limit = 50) =>
    fetchApi<import("./types/api").Transaction[]>(
      `/api/v1/transactions?limit=${limit}`
    ),
  updateCategory: (id: string, category: string) =>
    fetchApi<import("./types/api").Transaction>(
      `/api/v1/transactions/${id}/category`,
      { method: "PUT", body: JSON.stringify({ category }) }
    ),

  // ─── Budget ───
  getMonthlyBudget: (months = 12) =>
    fetchApi<import("./types/api").MonthlyBudget[]>(
      `/api/v1/budget/monthly?limit=${months}`
    ),
  getCategorySpending: (months = 3) =>
    fetchApi<import("./types/api").CategorySpending[]>(
      `/api/v1/budget/categories?limit=${months}`
    ),
  getCategoryTransactions: (category: string, months = 3) =>
    fetchApi<import("./types/api").CategoryTransaction[]>(
      `/api/v1/budget/categories/${encodeURIComponent(category)}/transactions?months=${months}`
    ),

  // ─── Market ───
  getQuote: (ticker: string) =>
    fetchApi<import("./types/api").PriceHistory[]>(
      `/api/v1/market/quote/${ticker}`
    ),
  getHistory: (ticker: string, limit = 365) =>
    fetchApi<import("./types/api").PriceHistory[]>(
      `/api/v1/market/history/${ticker}?limit=${limit}`
    ),
  getSparklines: () =>
    fetchApi<Record<string, number[]>>("/api/v1/market/sparklines"),
  getFxRates: () =>
    fetchApi<import("./types/api").ExchangeRate[]>("/api/v1/market/fx"),

  // ─── Analytics ───
  getDiversification: () =>
    fetchApi<import("./types/api").DiversificationScore>(
      "/api/v1/analytics/diversification"
    ),

  // ─── Loans ───
  getLoans: () =>
    fetchApi<import("./types/api").Loan[]>("/api/v1/loans"),

  // ─── SCA ───
  getSCA: () =>
    fetchApi<import("./types/api").SCA>("/api/v1/sca"),

  // ─── Costs ───
  getCosts: () =>
    fetchApi<Record<string, unknown>>("/api/v1/costs"),

  // ─── Insights ───
  getInsightsRules: () =>
    fetchApi<Record<string, unknown>[]>("/api/v1/insights/rules"),
  getBudgetProjections: () =>
    fetchApi<Record<string, unknown>>("/api/v1/budget/projections"),
  getLoansAnalysis: () =>
    fetchApi<Record<string, unknown>>("/api/v1/loans/analysis"),

  // ─── Patrimoine ───
  getPatrimoine: () =>
    fetchApi<Record<string, unknown>>("/api/v1/patrimoine"),

  // ─── Alerts ───
  getAlerts: () =>
    fetchApi<import("./types/api").PriceAlert[]>("/api/v1/alerts"),
  createAlert: (ticker: string, alert_type: string, threshold: number) =>
    fetchApi<import("./types/api").PriceAlert>("/api/v1/alerts", {
      method: "POST",
      body: JSON.stringify({ ticker, alert_type, threshold }),
    }),
  deleteAlert: (id: string) =>
    fetchApi<void>(`/api/v1/alerts/${id}`, { method: "DELETE" }),
};
