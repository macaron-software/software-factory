import { describe, it, expect } from "vitest";
import { useAppStore } from "../lib/store";

describe("AppStore", () => {
  it("has default period 1Y", () => {
    const state = useAppStore.getState();
    expect(state.selectedPeriod).toBe("1Y");
  });

  it("can change period", () => {
    useAppStore.getState().setPeriod("3M");
    expect(useAppStore.getState().selectedPeriod).toBe("3M");
    // Reset
    useAppStore.getState().setPeriod("1Y");
  });

  it("has default currency EUR", () => {
    expect(useAppStore.getState().currency).toBe("EUR");
  });

  it("can toggle sidebar", () => {
    const initial = useAppStore.getState().sidebarOpen;
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarOpen).toBe(!initial);
    // Reset
    useAppStore.getState().toggleSidebar();
  });
});
