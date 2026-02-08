import type { NetWorthHistory, MonthlyBudget, CategorySpending } from "./types/api";

/** Generate realistic net worth history for demo. */
export function generateNetWorthHistory(days = 365): NetWorthHistory[] {
  const now = new Date();
  const data: NetWorthHistory[] = [];

  // Start values
  let cash = 165000;
  let savings = 30000;
  let investments = 78000;
  const realEstate = 0;

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);

    // Simulate daily variations
    cash += (Math.random() - 0.48) * 200;
    savings += (Math.random() - 0.45) * 80;
    investments += (Math.random() - 0.42) * 600;

    // Monthly salary bump (1st of month)
    if (d.getDate() === 1) {
      cash += 4800 + Math.random() * 400;
    }
    // Monthly expenses spread
    if (d.getDate() === 5) cash -= 1200 + Math.random() * 200;
    if (d.getDate() === 15) cash -= 800 + Math.random() * 300;
    if (d.getDate() === 25) cash -= 600 + Math.random() * 200;

    // Monthly savings transfer
    if (d.getDate() === 2) {
      const transfer = 500 + Math.random() * 200;
      cash -= transfer;
      savings += transfer;
    }

    // Quarterly investment
    if (d.getDate() === 1 && d.getMonth() % 3 === 0) {
      const invest = 1500 + Math.random() * 500;
      cash -= invest;
      investments += invest;
    }

    const totalAssets = cash + savings + investments + realEstate;
    const totalLiabilities = 185000;

    data.push({
      date: d.toISOString().split("T")[0],
      total_assets: Math.round(totalAssets * 100) / 100,
      total_liabilities: totalLiabilities,
      net_worth: Math.round((totalAssets - totalLiabilities) * 100) / 100,
      breakdown: {
        cash: Math.round(cash * 100) / 100,
        savings: Math.round(savings * 100) / 100,
        investments: Math.round(investments * 100) / 100,
        real_estate: realEstate,
      },
    });
  }

  return data;
}

/** Generate realistic monthly budget data. */
export function generateMonthlyBudget(months = 12): MonthlyBudget[] {
  const now = new Date();
  const data: MonthlyBudget[] = [];

  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const month = d.toISOString().slice(0, 7);

    const income = 4800 + Math.random() * 800;
    const expenses = 2600 + Math.random() * 1400;
    const savingsRate = ((income - expenses) / income) * 100;

    data.push({
      month,
      income: Math.round(income * 100) / 100,
      expenses: Math.round(expenses * 100) / 100,
      savings_rate: Math.round(savingsRate * 100) / 100,
    });
  }

  return data;
}

/** Generate realistic category spending. */
export function generateCategorySpending(): CategorySpending[] {
  return [
    { category: "logement", total: 3850, count: 6 },
    { category: "alimentation", total: 1420, count: 45 },
    { category: "transport", total: 680, count: 18 },
    { category: "abonnements", total: 520, count: 12 },
    { category: "restauration", total: 480, count: 22 },
    { category: "shopping", total: 390, count: 8 },
    { category: "sante", total: 280, count: 5 },
    { category: "energie", total: 210, count: 3 },
    { category: "telecom", total: 120, count: 3 },
    { category: "assurance", total: 95, count: 2 },
  ];
}

/** Generate sparkline data (30 points normalized). */
export function generateSparkline(currentPrice: number, volatility = 0.02): number[] {
  const points: number[] = [];
  let price = currentPrice * (1 - volatility * 15 * (Math.random() - 0.4));
  for (let i = 0; i < 30; i++) {
    price *= 1 + (Math.random() - 0.48) * volatility;
    points.push(Math.round(price * 100) / 100);
  }
  // Ensure last point is close to current price
  points[29] = currentPrice;
  return points;
}
