import { create } from "zustand";

interface AppState {
  selectedPeriod: "1M" | "3M" | "6M" | "YTD" | "1Y" | "3Y" | "MAX";
  setPeriod: (period: AppState["selectedPeriod"]) => void;
  currency: "EUR" | "native";
  setCurrency: (c: "EUR" | "native") => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  privacyMode: boolean;
  togglePrivacy: () => void;
}

const getInitialPrivacy = (): boolean => {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("finary_privacy") === "1";
};

export const useAppStore = create<AppState>((set) => ({
  selectedPeriod: "1Y",
  setPeriod: (period) => set({ selectedPeriod: period }),
  currency: "EUR",
  setCurrency: (currency) => set({ currency }),
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  privacyMode: getInitialPrivacy(),
  togglePrivacy: () =>
    set((s) => {
      const next = !s.privacyMode;
      localStorage.setItem("finary_privacy", next ? "1" : "0");
      document.documentElement.setAttribute("data-privacy", next ? "on" : "off");
      return { privacyMode: next };
    }),
}));
