use axum::{
    Json,
    extract::{Path, State},
};
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

use crate::db;
use crate::models::*;
use crate::services;
use crate::AppState;

pub async fn get_portfolio(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<PositionValuation>>, (axum::http::StatusCode, String)> {
    let positions = db::get_all_positions(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let fx_rows = db::get_latest_fx_rates(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let mut fx_rates: HashMap<String, Decimal> = HashMap::new();
    fx_rates.insert("EUR".to_string(), Decimal::ONE);
    for r in &fx_rows {
        fx_rates.insert(r.quote_currency.clone(), r.rate);
    }

    let (valuations, _) = services::value_positions(&positions, &fx_rates);
    Ok(Json(valuations))
}

pub async fn get_position(
    State(state): State<Arc<AppState>>,
    Path(id): Path<Uuid>,
) -> Result<Json<Position>, (axum::http::StatusCode, String)> {
    db::get_position_by_id(&state.db, id)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
        .map(Json)
        .ok_or((axum::http::StatusCode::NOT_FOUND, "Position not found".to_string()))
}

pub async fn get_allocation(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Allocation>, (axum::http::StatusCode, String)> {
    let positions = db::get_all_positions(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let fx_rows = db::get_latest_fx_rates(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let mut fx_rates: HashMap<String, Decimal> = HashMap::new();
    fx_rates.insert("EUR".to_string(), Decimal::ONE);
    for r in &fx_rows {
        fx_rates.insert(r.quote_currency.clone(), r.rate);
    }

    let (valuations, total) = services::value_positions(&positions, &fx_rates);

    let compute_allocation = |key_fn: &dyn Fn(&PositionValuation) -> String| -> Vec<AllocationItem> {
        let mut map: HashMap<String, Decimal> = HashMap::new();
        for v in &valuations {
            let key = key_fn(v);
            *map.entry(key).or_insert(Decimal::ZERO) += v.value_eur;
        }
        let mut items: Vec<_> = map
            .into_iter()
            .map(|(label, value)| AllocationItem {
                label,
                value_eur: value,
                percentage: if total > Decimal::ZERO {
                    (value / total * Decimal::from(100)).round_dp(2)
                } else {
                    Decimal::ZERO
                },
            })
            .collect();
        items.sort_by(|a, b| b.value_eur.cmp(&a.value_eur));
        items
    };

    Ok(Json(Allocation {
        by_sector: compute_allocation(&|v| {
            v.position.sector.clone().unwrap_or_else(|| "Other".to_string())
        }),
        by_country: compute_allocation(&|v| {
            v.position.country.clone().unwrap_or_else(|| "Other".to_string())
        }),
        by_currency: compute_allocation(&|v| {
            v.position.currency.clone().unwrap_or_else(|| "EUR".to_string())
        }),
        by_asset_type: compute_allocation(&|v| v.position.asset_type.clone()),
    }))
}

pub async fn get_performance(
    State(_state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    // Placeholder: performance calculation requires historical data
    Json(serde_json::json!({
        "twr_ytd": null,
        "twr_1y": null,
        "message": "Performance calculation requires historical position snapshots"
    }))
}

pub async fn get_dividends(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<Dividend>>, (axum::http::StatusCode, String)> {
    db::get_all_dividends(&state.db)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}
