import { create } from "zustand";

interface AppState {
  selectedPeriod: "1M" | "3M" | "6M" | "YTD" | "1Y" | "3Y" | "MAX";
  setPeriod: (period: AppState["selectedPeriod"]) => void;
  currency: "EUR" | "native";
  setCurrency: (c: "EUR" | "native") => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedPeriod: "1Y",
  setPeriod: (period) => set({ selectedPeriod: period }),
  currency: "EUR",
  setCurrency: (currency) => set({ currency }),
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
