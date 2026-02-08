use axum::{
    Json,
    extract::{Path, Query, State},
};
use std::sync::Arc;
use uuid::Uuid;

use crate::db;
use crate::models::*;
use crate::AppState;

pub async fn list_transactions(
    State(state): State<Arc<AppState>>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<Vec<Transaction>>, (axum::http::StatusCode, String)> {
    let limit = params.limit.unwrap_or(50).min(200);
    db::get_all_transactions(&state.db, limit)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn update_category(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
    Json(body): Json<UpdateCategory>,
) -> Result<Json<Transaction>, (axum::http::StatusCode, String)> {
    db::update_transaction_category(&state.db, id, &body.category)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
        .map(Json)
        .ok_or((axum::http::StatusCode::NOT_FOUND, "Transaction not found".to_string()))
}
