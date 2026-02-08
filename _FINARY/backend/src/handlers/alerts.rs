use axum::{
    Json,
    extract::{Path, State},
};
use std::sync::Arc;
use uuid::Uuid;

use crate::db;
use crate::models::*;
use crate::AppState;

pub async fn list_alerts(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<PriceAlert>>, (axum::http::StatusCode, String)> {
    db::get_active_alerts(&state.db)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn create_alert(
    State(state): State<Arc<AppState>>,
    Json(body): Json<CreateAlert>,
) -> Result<(axum::http::StatusCode, Json<PriceAlert>), (axum::http::StatusCode, String)> {
    db::create_price_alert(&state.db, &body)
        .await
        .map(|alert| (axum::http::StatusCode::CREATED, Json(alert)))
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

pub async fn delete_alert(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<axum::http::StatusCode, (axum::http::StatusCode, String)> {
    let deleted = db::delete_price_alert(&state.db, id)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    if deleted {
        Ok(axum::http::StatusCode::NO_CONTENT)
    } else {
        Err((axum::http::StatusCode::NOT_FOUND, "Alert not found".to_string()))
    }
}
