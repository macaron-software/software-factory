use axum::{
    Json,
    extract::{Path, Query, State},
};
use std::sync::Arc;
use uuid::Uuid;

use crate::db;
use crate::models::*;
use crate::AppState;

pub async fn list_accounts(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<Account>>, (axum::http::StatusCode, String)> {
    db::get_all_accounts(&state.db)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn get_account(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<Account>, (axum::http::StatusCode, String)> {
    db::get_account_by_id(&state.db, id)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
        .map(Json)
        .ok_or((axum::http::StatusCode::NOT_FOUND, "Account not found".to_string()))
}

pub async fn get_account_transactions(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<Vec<Transaction>>, (axum::http::StatusCode, String)> {
    let limit = params.limit.unwrap_or(50).min(200);
    db::get_transactions_for_account(&state.db, id, limit)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}
