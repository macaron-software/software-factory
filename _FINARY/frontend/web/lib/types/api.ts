// ─── API Types ───

export interface Account {
  id: string;
  institution_id: string | null;
  external_id: string | null;
  name: string;
  account_type: AccountType;
  currency: string;
  balance: number;
  is_pro: boolean;
  updated_at: string;
}

export type AccountType =
  | "checking"
  | "savings"
  | "pea"
  | "cto"
  | "av"
  | "loan"
  | "crypto";

export interface Transaction {
  id: string;
  account_id: string;
  external_id: string | null;
  date: string;
  description: string;
  amount: number;
  category: string | null;
  category_manual: string | null;
  merchant: string | null;
}

export interface Position {
  id: string;
  account_id: string;
  ticker: string;
  isin: string | null;
  name: string;
  quantity: number;
  avg_cost: number | null;
  current_price: number | null;
  currency: string;
  asset_type: string;
  sector: string | null;
  country: string | null;
}

export interface PositionValuation extends Position {
  value_native: number;
  value_eur: number;
  pnl_native: number;
  pnl_eur: number;
  pnl_pct: number;
  weight_pct: number;
}

export interface NetWorthSummary {
  net_worth: number;
  total_assets: number;
  total_liabilities: number;
  breakdown: {
    cash: number;
    savings: number;
    investments: number;
    real_estate: number;
  };
  by_institution: { name: string; display_name: string; total: number }[];
  variation_day: number | null;
  variation_month: number | null;
}

export interface NetWorthHistory {
  date: string;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  breakdown: Record<string, number>;
}

export interface Allocation {
  by_sector: AllocationItem[];
  by_country: AllocationItem[];
  by_currency: AllocationItem[];
  by_asset_type: AllocationItem[];
}

export interface AllocationItem {
  label: string;
  value_eur: number;
  percentage: number;
}

export interface MonthlyBudget {
  month: string;
  income: number;
  expenses: number;
  savings_rate: number;
}

export interface CategorySpending {
  category: string;
  total: number;
  count: number;
}

export interface Dividend {
  id: string;
  position_id: string;
  ex_date: string | null;
  pay_date: string | null;
  amount_per_share: number;
  total_amount: number;
  currency: string;
}

export interface ExchangeRate {
  date: string;
  base_currency: string;
  quote_currency: string;
  rate: number;
}

export interface PriceAlert {
  id: string;
  ticker: string;
  alert_type: "above" | "below";
  threshold: number;
  is_active: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface DiversificationScore {
  score: number;
  max_score: number;
  details: {
    num_positions: number;
    num_sectors: number;
    num_countries: number;
    max_weight_pct: number;
    max_weight_ticker: string;
  };
}

export interface PriceHistory {
  ticker: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  currency: string;
}
