---
name: rust-api
description: Rust/Axum API patterns for personal finance endpoints. Use when building or modifying the Finary backend API. Covers SQLx queries, financial calculations (P&L, TWR, MWR), pagination, caching, and all REST endpoints for accounts, portfolio, budget, and net worth.
---

# Rust API (Axum + SQLx)

Backend API pour l'agrégation patrimoniale.

## Project Setup

```toml
# Cargo.toml
[dependencies]
axum = "0.8"
tokio = { version = "1", features = ["full"] }
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "uuid", "decimal", "chrono", "json"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
rust_decimal = { version = "1", features = ["db-postgres", "serde-with-str"] }
redis = { version = "0.27", features = ["tokio-comp"] }
tower-http = { version = "0.6", features = ["cors", "trace"] }
tracing = "0.1"
tracing-subscriber = "0.3"
```

## Router Structure

```rust
use axum::{Router, routing::get};

pub fn create_router(state: AppState) -> Router {
    Router::new()
        // Net Worth
        .route("/api/v1/networth", get(handlers::networth::get_networth))
        .route("/api/v1/networth/breakdown", get(handlers::networth::get_breakdown))
        // Accounts
        .route("/api/v1/accounts", get(handlers::accounts::list_accounts))
        .route("/api/v1/accounts/:id", get(handlers::accounts::get_account))
        .route("/api/v1/accounts/:id/transactions", get(handlers::accounts::get_transactions))
        // Portfolio
        .route("/api/v1/portfolio", get(handlers::portfolio::get_portfolio))
        .route("/api/v1/portfolio/performance", get(handlers::portfolio::get_performance))
        .route("/api/v1/portfolio/allocation", get(handlers::portfolio::get_allocation))
        .route("/api/v1/portfolio/dividends", get(handlers::portfolio::get_dividends))
        // Budget
        .route("/api/v1/budget/monthly", get(handlers::budget::get_monthly))
        .route("/api/v1/budget/categories", get(handlers::budget::get_categories))
        // Sync
        .route("/api/v1/sync", axum::routing::post(handlers::sync::trigger_sync))
        .route("/api/v1/sync/status", get(handlers::sync::get_status))
        .with_state(state)
}
```

## SQLx Patterns

```rust
use sqlx::FromRow;
use rust_decimal::Decimal;
use chrono::{NaiveDate, DateTime, Utc};
use uuid::Uuid;

#[derive(Debug, FromRow, Serialize)]
pub struct Account {
    pub id: Uuid,
    pub institution_id: Uuid,
    pub name: String,
    pub account_type: String,
    pub currency: String,
    pub balance: Decimal,
    pub is_pro: bool,
    pub updated_at: DateTime<Utc>,
}

// Toujours utiliser des query macros typées
pub async fn list_accounts(pool: &PgPool) -> Result<Vec<Account>> {
    sqlx::query_as!(
        Account,
        r#"
        SELECT id, institution_id, name, account_type, currency, 
               balance, is_pro, updated_at
        FROM accounts 
        ORDER BY institution_id, name
        "#
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}
```

## Calculs Financiers

```rust
/// P&L d'une position
pub fn calculate_pnl(quantity: Decimal, avg_cost: Decimal, current_price: Decimal) -> PnL {
    let cost_basis = quantity * avg_cost;
    let market_value = quantity * current_price;
    let pnl_amount = market_value - cost_basis;
    let pnl_pct = if cost_basis > Decimal::ZERO {
        (pnl_amount / cost_basis) * Decimal::from(100)
    } else {
        Decimal::ZERO
    };
    PnL { cost_basis, market_value, pnl_amount, pnl_pct }
}

/// TWR (Time-Weighted Return) — pas affecté par les flux
pub fn calculate_twr(snapshots: &[(NaiveDate, Decimal, Decimal)]) -> Decimal {
    // snapshots: (date, valeur_portefeuille, flux_net_du_jour)
    let mut twr = Decimal::ONE;
    for window in snapshots.windows(2) {
        let (_, prev_value, _) = window[0];
        let (_, curr_value, cash_flow) = window[1];
        if prev_value + cash_flow > Decimal::ZERO {
            let period_return = (curr_value - prev_value - cash_flow) / (prev_value + cash_flow);
            twr *= Decimal::ONE + period_return;
        }
    }
    (twr - Decimal::ONE) * Decimal::from(100)
}
```

## Pagination Cursor-Based

```rust
#[derive(Deserialize)]
pub struct PaginationParams {
    pub cursor: Option<Uuid>,   // ID de la dernière transaction vue
    pub limit: Option<i64>,     // default 50, max 200
}

pub async fn get_transactions(
    pool: &PgPool,
    account_id: Uuid,
    params: PaginationParams,
) -> Result<PaginatedResponse<Transaction>> {
    let limit = params.limit.unwrap_or(50).min(200);
    
    let items = if let Some(cursor) = params.cursor {
        sqlx::query_as!(Transaction,
            "SELECT * FROM transactions 
             WHERE account_id = $1 AND id < $2
             ORDER BY date DESC, id DESC LIMIT $3",
            account_id, cursor, limit + 1
        ).fetch_all(pool).await?
    } else {
        sqlx::query_as!(Transaction,
            "SELECT * FROM transactions 
             WHERE account_id = $1
             ORDER BY date DESC, id DESC LIMIT $2",
            account_id, limit + 1
        ).fetch_all(pool).await?
    };
    
    let has_more = items.len() > limit as usize;
    let items: Vec<_> = items.into_iter().take(limit as usize).collect();
    let next_cursor = if has_more { items.last().map(|t| t.id) } else { None };
    
    Ok(PaginatedResponse { items, next_cursor, has_more })
}
```

## Cache Redis

```rust
// Cache net worth (refresh après chaque sync)
const NETWORTH_CACHE_KEY: &str = "finary:networth";
const CACHE_TTL: u64 = 3600; // 1h

pub async fn get_cached_networth(redis: &redis::Client) -> Option<NetWorth> {
    let mut conn = redis.get_multiplexed_async_connection().await.ok()?;
    let cached: Option<String> = redis::cmd("GET")
        .arg(NETWORTH_CACHE_KEY)
        .query_async(&mut conn).await.ok()?;
    cached.and_then(|s| serde_json::from_str(&s).ok())
}

pub async fn invalidate_cache(redis: &redis::Client) {
    if let Ok(mut conn) = redis.get_multiplexed_async_connection().await {
        let _: () = redis::cmd("DEL")
            .arg(NETWORTH_CACHE_KEY)
            .query_async(&mut conn).await.unwrap_or(());
    }
}
```

## Error Handling

```rust
use axum::{http::StatusCode, response::IntoResponse, Json};

pub enum AppError {
    NotFound(String),
    Database(sqlx::Error),
    Internal(anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> axum::response::Response {
        let (status, message) = match self {
            AppError::NotFound(msg) => (StatusCode::NOT_FOUND, msg),
            AppError::Database(e) => {
                tracing::error!("Database error: {e}");
                (StatusCode::INTERNAL_SERVER_ERROR, "Database error".into())
            }
            AppError::Internal(e) => {
                tracing::error!("Internal error: {e}");
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal error".into())
            }
        };
        (status, Json(serde_json::json!({"error": message}))).into_response()
    }
}
```
