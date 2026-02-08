use axum::{
    Json,
    extract::State,
};
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::sync::Arc;

use crate::db;
use crate::services;
use crate::AppState;

#[derive(serde::Serialize)]
pub struct DiversificationResponse {
    pub score: u32,
    pub max_score: u32,
    pub details: DiversificationDetails,
}

#[derive(serde::Serialize)]
pub struct DiversificationDetails {
    pub num_positions: usize,
    pub num_sectors: usize,
    pub num_countries: usize,
    pub max_weight_pct: Decimal,
    pub max_weight_ticker: String,
}

pub async fn get_diversification(
    State(state): State<Arc<AppState>>,
) -> Result<Json<DiversificationResponse>, (axum::http::StatusCode, String)> {
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
    let score = services::diversification_score(&valuations);

    let sectors: std::collections::HashSet<_> = valuations
        .iter()
        .filter_map(|v| v.position.sector.as_deref())
        .collect();
    let countries: std::collections::HashSet<_> = valuations
        .iter()
        .filter_map(|v| v.position.country.as_deref())
        .collect();

    let (max_ticker, max_weight) = valuations
        .iter()
        .max_by_key(|v| v.weight_pct)
        .map(|v| (v.position.ticker.clone(), v.weight_pct))
        .unwrap_or(("".to_string(), Decimal::ZERO));

    Ok(Json(DiversificationResponse {
        score,
        max_score: 100,
        details: DiversificationDetails {
            num_positions: valuations.len(),
            num_sectors: sectors.len(),
            num_countries: countries.len(),
            max_weight_pct: max_weight,
            max_weight_ticker: max_ticker,
        },
    }))
}
