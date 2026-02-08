use sqlx::PgPool;
use uuid::Uuid;

use crate::models::*;

// ─── Accounts ───

pub async fn get_all_accounts(pool: &PgPool) -> Result<Vec<Account>, sqlx::Error> {
    sqlx::query_as::<_, Account>("SELECT * FROM accounts ORDER BY name")
        .fetch_all(pool)
        .await
}

pub async fn get_account_by_id(pool: &PgPool, id: Uuid) -> Result<Option<Account>, sqlx::Error> {
    sqlx::query_as::<_, Account>("SELECT * FROM accounts WHERE id = $1")
        .bind(id)
        .fetch_optional(pool)
        .await
}

pub async fn get_transactions_for_account(
    pool: &PgPool,
    account_id: Uuid,
    limit: i64,
) -> Result<Vec<Transaction>, sqlx::Error> {
    sqlx::query_as::<_, Transaction>(
        "SELECT * FROM transactions WHERE account_id = $1 ORDER BY date DESC LIMIT $2",
    )
    .bind(account_id)
    .bind(limit)
    .fetch_all(pool)
    .await
}

// ─── Positions ───

pub async fn get_all_positions(pool: &PgPool) -> Result<Vec<Position>, sqlx::Error> {
    sqlx::query_as::<_, Position>("SELECT * FROM positions ORDER BY name")
        .fetch_all(pool)
        .await
}

pub async fn get_position_by_id(
    pool: &PgPool,
    id: Uuid,
) -> Result<Option<Position>, sqlx::Error> {
    sqlx::query_as::<_, Position>("SELECT * FROM positions WHERE id = $1")
        .bind(id)
        .fetch_optional(pool)
        .await
}

// ─── Dividends ───

pub async fn get_all_dividends(pool: &PgPool) -> Result<Vec<Dividend>, sqlx::Error> {
    sqlx::query_as::<_, Dividend>(
        "SELECT d.* FROM dividends d JOIN positions p ON d.position_id = p.id ORDER BY d.pay_date DESC",
    )
    .fetch_all(pool)
    .await
}

// ─── Transactions ───

pub async fn get_all_transactions(
    pool: &PgPool,
    limit: i64,
) -> Result<Vec<Transaction>, sqlx::Error> {
    sqlx::query_as::<_, Transaction>(
        "SELECT * FROM transactions ORDER BY date DESC LIMIT $1",
    )
    .bind(limit)
    .fetch_all(pool)
    .await
}

pub async fn update_transaction_category(
    pool: &PgPool,
    id: Uuid,
    category: &str,
) -> Result<Option<Transaction>, sqlx::Error> {
    sqlx::query_as::<_, Transaction>(
        "UPDATE transactions SET category_manual = $2 WHERE id = $1 RETURNING *",
    )
    .bind(id)
    .bind(category)
    .fetch_optional(pool)
    .await
}

// ─── Net Worth ───

pub async fn get_networth_history(
    pool: &PgPool,
    limit: i64,
) -> Result<Vec<NetWorthHistory>, sqlx::Error> {
    sqlx::query_as::<_, NetWorthHistory>(
        "SELECT * FROM networth_history ORDER BY date DESC LIMIT $1",
    )
    .bind(limit)
    .fetch_all(pool)
    .await
}

// ─── Institutions ───

pub async fn get_all_institutions(pool: &PgPool) -> Result<Vec<Institution>, sqlx::Error> {
    sqlx::query_as::<_, Institution>(
        "SELECT id, name, display_name, scraper_type, last_sync_at, sync_status FROM institutions ORDER BY name",
    )
    .fetch_all(pool)
    .await
}

// ─── Price History ───

pub async fn get_price_history(
    pool: &PgPool,
    ticker: &str,
    limit: i64,
) -> Result<Vec<PriceHistory>, sqlx::Error> {
    sqlx::query_as::<_, PriceHistory>(
        "SELECT * FROM price_history WHERE ticker = $1 ORDER BY date DESC LIMIT $2",
    )
    .bind(ticker)
    .bind(limit)
    .fetch_all(pool)
    .await
}

// ─── Exchange Rates ───

pub async fn get_latest_fx_rates(pool: &PgPool) -> Result<Vec<ExchangeRate>, sqlx::Error> {
    sqlx::query_as::<_, ExchangeRate>(
        "SELECT DISTINCT ON (quote_currency) * FROM exchange_rates ORDER BY quote_currency, date DESC",
    )
    .fetch_all(pool)
    .await
}

// ─── Sync Logs ───

pub async fn get_sync_logs(pool: &PgPool, limit: i64) -> Result<Vec<SyncLog>, sqlx::Error> {
    sqlx::query_as::<_, SyncLog>(
        "SELECT * FROM sync_logs ORDER BY started_at DESC LIMIT $1",
    )
    .bind(limit)
    .fetch_all(pool)
    .await
}

// ─── Alerts ───

pub async fn get_active_alerts(pool: &PgPool) -> Result<Vec<PriceAlert>, sqlx::Error> {
    sqlx::query_as::<_, PriceAlert>(
        "SELECT * FROM price_alerts WHERE is_active = true ORDER BY created_at DESC",
    )
    .fetch_all(pool)
    .await
}

pub async fn create_price_alert(
    pool: &PgPool,
    alert: &CreateAlert,
) -> Result<PriceAlert, sqlx::Error> {
    sqlx::query_as::<_, PriceAlert>(
        "INSERT INTO price_alerts (ticker, alert_type, threshold) VALUES ($1, $2, $3) RETURNING *",
    )
    .bind(&alert.ticker)
    .bind(&alert.alert_type)
    .bind(alert.threshold)
    .fetch_one(pool)
    .await
}

pub async fn delete_price_alert(pool: &PgPool, id: Uuid) -> Result<bool, sqlx::Error> {
    let result = sqlx::query("DELETE FROM price_alerts WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await?;
    Ok(result.rows_affected() > 0)
}

// ─── Budget ───

pub async fn get_monthly_budget(
    pool: &PgPool,
    months: i64,
) -> Result<Vec<MonthlyBudget>, sqlx::Error> {
    let rows = sqlx::query_as::<_, (String, Option<rust_decimal::Decimal>, Option<rust_decimal::Decimal>)>(
        r#"
        SELECT
            to_char(date_trunc('month', date), 'YYYY-MM') as month,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as expenses
        FROM transactions
        WHERE date >= (CURRENT_DATE - ($1 || ' months')::interval)
        GROUP BY date_trunc('month', date)
        ORDER BY month DESC
        "#,
    )
    .bind(months.to_string())
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|(month, income, expenses)| {
            let inc = income.unwrap_or_default();
            let exp = expenses.unwrap_or_default();
            let rate = if inc > rust_decimal::Decimal::ZERO {
                (inc - exp) / inc * rust_decimal::Decimal::from(100)
            } else {
                rust_decimal::Decimal::ZERO
            };
            MonthlyBudget {
                month,
                income: inc,
                expenses: exp,
                savings_rate: rate,
            }
        })
        .collect())
}

pub async fn get_category_spending(
    pool: &PgPool,
    months: i64,
) -> Result<Vec<CategorySpending>, sqlx::Error> {
    sqlx::query_as::<_, (Option<String>, Option<rust_decimal::Decimal>, i64)>(
        r#"
        SELECT
            COALESCE(category_manual, category, 'non_categorise') as cat,
            SUM(ABS(amount)) as total,
            COUNT(*) as count
        FROM transactions
        WHERE amount < 0 AND date >= (CURRENT_DATE - ($1 || ' months')::interval)
        GROUP BY cat
        ORDER BY total DESC
        "#,
    )
    .bind(months.to_string())
    .fetch_all(pool)
    .await
    .map(|rows| {
        rows.into_iter()
            .map(|(cat, total, count)| CategorySpending {
                category: cat.unwrap_or_else(|| "non_categorise".to_string()),
                total: total.unwrap_or_default(),
                count,
            })
            .collect()
    })
}
