use axum::{Json, extract::State};
use std::sync::Arc;
use crate::{db, models::Institution, AppState};

pub async fn list_institutions(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<Institution>>, (axum::http::StatusCode, String)> {
    let institutions = db::get_all_institutions(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(institutions))
}
