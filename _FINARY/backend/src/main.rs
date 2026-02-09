mod db;
mod handlers;
mod models;
mod services;

use axum::{
    Json, Router,
    routing::get,
};
use sqlx::postgres::PgPoolOptions;
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;

pub struct AppState {
    pub db: sqlx::PgPool,
}

async fn health_check() -> Json<serde_json::Value> {
    Json(serde_json::json!({"status": "ok", "engine": "rust"}))
}

pub fn create_router(state: Arc<AppState>) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        // Net worth
        .route("/api/v1/networth", get(handlers::networth::get_networth))
        .route(
            "/api/v1/networth/history",
            get(handlers::networth::get_networth_history),
        )
        // Accounts
        .route("/api/v1/accounts", get(handlers::accounts::list_accounts))
        .route(
            "/api/v1/accounts/{id}",
            get(handlers::accounts::get_account),
        )
        .route(
            "/api/v1/accounts/{id}/transactions",
            get(handlers::accounts::get_account_transactions),
        )
        // Portfolio
        .route(
            "/api/v1/portfolio",
            get(handlers::portfolio::get_portfolio),
        )
        .route(
            "/api/v1/portfolio/allocation",
            get(handlers::portfolio::get_allocation),
        )
        .route(
            "/api/v1/portfolio/performance",
            get(handlers::portfolio::get_performance),
        )
        .route(
            "/api/v1/portfolio/dividends",
            get(handlers::portfolio::get_dividends),
        )
        // Positions
        .route(
            "/api/v1/positions/{id}",
            get(handlers::portfolio::get_position),
        )
        // Transactions
        .route(
            "/api/v1/transactions",
            get(handlers::transactions::list_transactions),
        )
        .route(
            "/api/v1/transactions/{id}/category",
            axum::routing::put(handlers::transactions::update_category),
        )
        // Budget
        .route(
            "/api/v1/budget/monthly",
            get(handlers::budget::get_monthly),
        )
        .route(
            "/api/v1/budget/categories",
            get(handlers::budget::get_categories),
        )
        // Market
        .route(
            "/api/v1/market/quote/{ticker}",
            get(handlers::market::get_quote),
        )
        .route(
            "/api/v1/market/history/{ticker}",
            get(handlers::market::get_history),
        )
        .route("/api/v1/market/fx", get(handlers::market::get_fx_rates))
        .route(
            "/api/v1/market/search",
            get(handlers::market::search_ticker),
        )
        // Sync
        .route(
            "/api/v1/sync/status",
            get(handlers::sync::get_sync_status),
        )
        .route(
            "/api/v1/sync/logs",
            get(handlers::sync::get_sync_logs),
        )
        // Analytics
        .route(
            "/api/v1/analytics/diversification",
            get(handlers::analytics::get_diversification),
        )
        .route(
            "/api/v1/diversification",
            get(handlers::analytics::get_diversification),
        )
        // Institutions
        .route(
            "/api/v1/institutions",
            get(handlers::institutions::list_institutions),
        )
        // Alerts
        .route(
            "/api/v1/alerts",
            get(handlers::alerts::list_alerts)
                .post(handlers::alerts::create_alert),
        )
        .route(
            "/api/v1/alerts/{id}",
            axum::routing::delete(handlers::alerts::delete_alert),
        )
        // Health check
        .route("/api/v1/status", get(health_check))
        .with_state(state)
        .layer(cors)
        .layer(TraceLayer::new_for_http())
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    dotenvy::dotenv().ok();

    let database_url =
        std::env::var("DATABASE_URL").unwrap_or_else(|_| {
            "postgresql://finary:finary_dev@localhost:5433/finary".to_string()
        });

    let pool = PgPoolOptions::new()
        .max_connections(10)
        .connect(&database_url)
        .await
        .expect("Failed to connect to database");

    // Run migrations
    sqlx::migrate!("./migrations")
        .run(&pool)
        .await
        .expect("Failed to run migrations");

    let state = Arc::new(AppState { db: pool });
    let app = create_router(state);

    let addr = std::env::var("PORT").map(|p| format!("0.0.0.0:{p}")).unwrap_or_else(|_| "0.0.0.0:8001".to_string());
    tracing::info!("Finary API listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
