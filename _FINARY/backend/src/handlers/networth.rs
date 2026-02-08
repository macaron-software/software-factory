use axum::{
    Json,
    extract::{Query, State},
};
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

use crate::db;
use crate::models::*;
use crate::services;
use crate::AppState;

pub async fn get_networth(
    State(state): State<Arc<AppState>>,
) -> Result<Json<NetWorthSummary>, (axum::http::StatusCode, String)> {
    let accounts = db::get_all_accounts(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let positions = db::get_all_positions(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let fx_rows = db::get_latest_fx_rates(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let institutions = db::get_all_institutions(&state.db)
        .await
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let mut fx_rates: HashMap<String, Decimal> = HashMap::new();
    fx_rates.insert("EUR".to_string(), Decimal::ONE);
    for r in &fx_rows {
        fx_rates.insert(r.quote_currency.clone(), r.rate);
    }

    let (_, portfolio_total) = services::value_positions(&positions, &fx_rates);

    let mut cash = Decimal::ZERO;
    let mut savings = Decimal::ZERO;
    let mut loans = Decimal::ZERO;
    let mut by_inst: HashMap<Uuid, Decimal> = HashMap::new();

    for acc in &accounts {
        let currency = acc.currency.as_deref().unwrap_or("EUR");
        let balance_eur = to_eur(acc.balance, currency, &fx_rates);

        match acc.account_type.as_str() {
            "savings" => savings += balance_eur,
            "loan" => loans += balance_eur.abs(),
            _ => cash += balance_eur,
        }

        if let Some(inst_id) = acc.institution_id {
            *by_inst.entry(inst_id).or_insert(Decimal::ZERO) += balance_eur;
        }
    }

    let total_assets = cash + savings + portfolio_total;
    let total_liabilities = loans;

    let institution_balances: Vec<InstitutionBalance> = institutions
        .iter()
        .map(|i| InstitutionBalance {
            name: i.name.clone(),
            display_name: i.display_name.clone(),
            total: by_inst.get(&i.id).copied().unwrap_or(Decimal::ZERO),
        })
        .collect();

    Ok(Json(NetWorthSummary {
        net_worth: total_assets - total_liabilities,
        total_assets,
        total_liabilities,
        breakdown: BreakdownSummary {
            cash,
            savings,
            investments: portfolio_total,
            real_estate: Decimal::ZERO,
        },
        by_institution: institution_balances,
        variation_day: None,
        variation_month: None,
    }))
}

pub async fn get_networth_history(
    State(state): State<Arc<AppState>>,
    Query(params): Query<PaginationParams>,
) -> Result<Json<Vec<NetWorthHistory>>, (axum::http::StatusCode, String)> {
    let limit = params.limit.unwrap_or(365);
    db::get_networth_history(&state.db, limit)
        .await
        .map(Json)
        .map_err(|e| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))
}

fn to_eur(amount: Decimal, currency: &str, rates: &HashMap<String, Decimal>) -> Decimal {
    if currency == "EUR" {
        return amount;
    }
    let rate = rates.get(currency).copied().unwrap_or(Decimal::ONE);
    if rate == Decimal::ZERO {
        return amount;
    }
    (amount / rate).round_dp(2)
}
