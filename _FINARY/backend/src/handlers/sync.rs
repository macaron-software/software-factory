use axum::{
    Json,
    extract::State,
};
use std::sync::Arc;

use crate::db;
use crate::models::*;
use crate::AppState;

pub async fn get_sync_status(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<Institution>>, (axum::http::StatusCode, String)> {
    db::get_all_institutions(&state.db)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn get_sync_logs(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<SyncLog>>, (axum::http::StatusCode, String)> {
    db::get_sync_logs(&state.db, 50)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}
