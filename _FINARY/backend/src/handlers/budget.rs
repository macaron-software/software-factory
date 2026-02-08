use axum::{
    Json,
    extract::{Query, State},
};
use std::sync::Arc;

use crate::db;
use crate::models::*;
use crate::AppState;

pub async fn get_monthly(
    State(state): State<Arc<AppState>>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<Vec<MonthlyBudget>>, (axum::http::StatusCode, String)> {
    let months = params.limit.unwrap_or(12).min(60);
    db::get_monthly_budget(&state.db, months)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn get_categories(
    State(state): State<Arc<AppState>>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<Vec<CategorySpending>>, (axum::http::StatusCode, String)> {
    let months = params.limit.unwrap_or(3).min(24);
    db::get_category_spending(&state.db, months)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}
