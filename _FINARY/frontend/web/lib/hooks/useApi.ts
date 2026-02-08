import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ─── Net Worth ───

export function useNetWorth() {
  return useQuery({
    queryKey: ["networth"],
    queryFn: api.getNetWorth,
    refetchInterval: 5 * 60 * 1000, // 5min
  });
}

export function useNetWorthHistory(limit = 365) {
  return useQuery({
    queryKey: ["networth", "history", limit],
    queryFn: () => api.getNetWorthHistory(limit),
  });
}

// ─── Accounts ───

export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: api.getAccounts,
  });
}

export function useAccountTransactions(accountId: string, limit = 50) {
  return useQuery({
    queryKey: ["accounts", accountId, "transactions", limit],
    queryFn: () => api.getAccountTransactions(accountId, limit),
    enabled: !!accountId,
  });
}

// ─── Portfolio ───

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: api.getPortfolio,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useAllocation() {
  return useQuery({
    queryKey: ["portfolio", "allocation"],
    queryFn: api.getAllocation,
  });
}

export function useDividends() {
  return useQuery({
    queryKey: ["portfolio", "dividends"],
    queryFn: api.getDividends,
  });
}

// ─── Transactions ───

export function useTransactions(limit = 50) {
  return useQuery({
    queryKey: ["transactions", limit],
    queryFn: () => api.getTransactions(limit),
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, category }: { id: string; category: string }) =>
      api.updateCategory(id, category),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

// ─── Budget ───

export function useMonthlyBudget(months = 12) {
  return useQuery({
    queryKey: ["budget", "monthly", months],
    queryFn: () => api.getMonthlyBudget(months),
  });
}

export function useCategorySpending(months = 3) {
  return useQuery({
    queryKey: ["budget", "categories", months],
    queryFn: () => api.getCategorySpending(months),
  });
}

// ─── Market ───

export function usePriceHistory(ticker: string, limit = 365) {
  return useQuery({
    queryKey: ["market", "history", ticker, limit],
    queryFn: () => api.getHistory(ticker, limit),
    enabled: !!ticker,
  });
}

export function useFxRates() {
  return useQuery({
    queryKey: ["market", "fx"],
    queryFn: api.getFxRates,
    refetchInterval: 60 * 60 * 1000, // 1h
  });
}

// ─── Analytics ───

export function useDiversification() {
  return useQuery({
    queryKey: ["analytics", "diversification"],
    queryFn: api.getDiversification,
  });
}

// ─── Alerts ───

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: api.getAlerts,
  });
}
