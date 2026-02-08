use chrono::NaiveDate;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

// ─── Institutions ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct Institution {
    pub id: Uuid,
    pub name: String,
    pub display_name: String,
    pub scraper_type: String,
    pub last_sync_at: Option<chrono::DateTime<chrono::Utc>>,
    pub sync_status: Option<String>,
}

// ─── Accounts ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct Account {
    pub id: Uuid,
    pub institution_id: Option<Uuid>,
    pub external_id: Option<String>,
    pub name: String,
    pub account_type: String,
    pub currency: Option<String>,
    pub balance: Decimal,
    pub is_pro: Option<bool>,
    pub updated_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Serialize)]
pub struct AccountWithInstitution {
    #[serde(flatten)]
    pub account: Account,
    pub institution_name: Option<String>,
}

// ─── Transactions ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct Transaction {
    pub id: Uuid,
    pub account_id: Option<Uuid>,
    pub external_id: Option<String>,
    pub date: NaiveDate,
    pub description: String,
    pub amount: Decimal,
    pub category: Option<String>,
    pub category_manual: Option<String>,
    pub merchant: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateCategory {
    pub category: String,
}

// ─── Positions ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct Position {
    pub id: Uuid,
    pub account_id: Option<Uuid>,
    pub ticker: String,
    pub isin: Option<String>,
    pub name: String,
    pub quantity: Decimal,
    pub avg_cost: Option<Decimal>,
    pub current_price: Option<Decimal>,
    pub currency: Option<String>,
    pub asset_type: String,
    pub sector: Option<String>,
    pub country: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct PositionValuation {
    #[serde(flatten)]
    pub position: Position,
    pub value_native: Decimal,
    pub value_eur: Decimal,
    pub pnl_native: Decimal,
    pub pnl_eur: Decimal,
    pub pnl_pct: Decimal,
    pub weight_pct: Decimal,
}

// ─── Dividends ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct Dividend {
    pub id: Uuid,
    pub position_id: Option<Uuid>,
    pub ex_date: Option<NaiveDate>,
    pub pay_date: Option<NaiveDate>,
    pub amount_per_share: Option<Decimal>,
    pub total_amount: Option<Decimal>,
    pub currency: Option<String>,
}

// ─── Net Worth ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct NetWorthHistory {
    pub date: NaiveDate,
    pub total_assets: Option<Decimal>,
    pub total_liabilities: Option<Decimal>,
    pub net_worth: Option<Decimal>,
    pub breakdown: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub struct NetWorthSummary {
    pub net_worth: Decimal,
    pub total_assets: Decimal,
    pub total_liabilities: Decimal,
    pub breakdown: BreakdownSummary,
    pub by_institution: Vec<InstitutionBalance>,
    pub variation_day: Option<Decimal>,
    pub variation_month: Option<Decimal>,
}

#[derive(Debug, Serialize)]
pub struct BreakdownSummary {
    pub cash: Decimal,
    pub savings: Decimal,
    pub investments: Decimal,
    pub real_estate: Decimal,
}

#[derive(Debug, Serialize)]
pub struct InstitutionBalance {
    pub name: String,
    pub display_name: String,
    pub total: Decimal,
}

// ─── Price History ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct PriceHistory {
    pub ticker: String,
    pub date: NaiveDate,
    pub open: Option<Decimal>,
    pub high: Option<Decimal>,
    pub low: Option<Decimal>,
    pub close: Decimal,
    pub volume: Option<i64>,
    pub currency: Option<String>,
}

// ─── Exchange Rates ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct ExchangeRate {
    pub date: NaiveDate,
    pub base_currency: Option<String>,
    pub quote_currency: String,
    pub rate: Decimal,
}

// ─── Alerts ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct PriceAlert {
    pub id: Uuid,
    pub ticker: String,
    pub alert_type: String,
    pub threshold: Decimal,
    pub is_active: Option<bool>,
    pub triggered_at: Option<chrono::DateTime<chrono::Utc>>,
    pub created_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Deserialize)]
pub struct CreateAlert {
    pub ticker: String,
    pub alert_type: String,
    pub threshold: Decimal,
}

// ─── Sync ───

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct SyncLog {
    pub id: Uuid,
    pub institution_id: Option<Uuid>,
    pub started_at: Option<chrono::DateTime<chrono::Utc>>,
    pub finished_at: Option<chrono::DateTime<chrono::Utc>>,
    pub status: String,
    pub accounts_synced: Option<i32>,
    pub transactions_added: Option<i32>,
    pub error_message: Option<String>,
}

// ─── Budget ───

#[derive(Debug, Serialize)]
pub struct MonthlyBudget {
    pub month: String, // "2025-02"
    pub income: Decimal,
    pub expenses: Decimal,
    pub savings_rate: Decimal,
}

#[derive(Debug, Serialize)]
pub struct CategorySpending {
    pub category: String,
    pub total: Decimal,
    pub count: i64,
}

// ─── Allocation ───

#[derive(Debug, Serialize)]
pub struct AllocationItem {
    pub label: String,
    pub value_eur: Decimal,
    pub percentage: Decimal,
}

#[derive(Debug, Serialize)]
pub struct Allocation {
    pub by_sector: Vec<AllocationItem>,
    pub by_country: Vec<AllocationItem>,
    pub by_currency: Vec<AllocationItem>,
    pub by_asset_type: Vec<AllocationItem>,
}

// ─── Query params ───

#[derive(Debug, Deserialize)]
pub struct PaginationParams {
    pub cursor: Option<String>,
    pub limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct DateRangeParams {
    pub from: Option<NaiveDate>,
    pub to: Option<NaiveDate>,
}

#[derive(Debug, Deserialize)]
pub struct SearchParams {
    pub q: Option<String>,
}
