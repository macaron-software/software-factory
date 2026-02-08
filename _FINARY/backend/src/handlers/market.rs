use axum::{
    Json,
    extract::{Path, Query, State},
};
use std::sync::Arc;

use crate::db;
use crate::models::*;
use crate::AppState;

pub async fn get_quote(
    State(state): State<Arc<AppState>>,
    Path(ticker): Path<String>,
) -> Result<Json<Vec<PriceHistory>>, (axum::http::StatusCode, String)> {
    // Return latest price point
    db::get_price_history(&state.db, &ticker, 1)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn get_history(
    State(state): State<Arc<AppState>>,
    Path(ticker): Path<String>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<Vec<PriceHistory>>, (axum::http::StatusCode, String)> {
    let limit = params.limit.unwrap_or(365).min(5000);
    db::get_price_history(&state.db, &ticker, limit)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn get_fx_rates(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<ExchangeRate>>, (axum::http::StatusCode, String)> {
    db::get_latest_fx_rates(&state.db)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn search_ticker(
    State(_state): State<Arc<AppState>>,
    Query(params): Query<SearchParams>,
) -> Json<serde_json::Value> {
    // Placeholder: search would query isin_ticker_map + Yahoo Finance
    let query = params.q.unwrap_or_default();
    Json(serde_json::json!({
        "query": query,
        "results": [],
        "message": "Ticker search requires yfinance integration (Python service)"
    }))
}
