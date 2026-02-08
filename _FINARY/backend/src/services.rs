use rust_decimal::Decimal;
use std::collections::HashMap;

use crate::models::*;

/// Compute portfolio valuation with FX conversion to EUR.
pub fn value_positions(
    positions: &[Position],
    fx_rates: &HashMap<String, Decimal>,
) -> (Vec<PositionValuation>, Decimal) {
    let mut valuations = Vec::new();
    let mut total_eur = Decimal::ZERO;

    for pos in positions {
        let price = pos.current_price.unwrap_or(Decimal::ZERO);
        let qty = pos.quantity;
        let currency = pos.currency.as_deref().unwrap_or("EUR");

        let value_native = qty * price;
        let value_eur = to_eur(value_native, currency, fx_rates);

        let cost = pos.avg_cost.unwrap_or(Decimal::ZERO);
        let cost_native = qty * cost;
        let pnl_native = value_native - cost_native;
        let pnl_eur = to_eur(pnl_native, currency, fx_rates);
        let pnl_pct = if cost_native > Decimal::ZERO {
            (pnl_native / cost_native) * Decimal::from(100)
        } else {
            Decimal::ZERO
        };

        total_eur += value_eur;

        valuations.push(PositionValuation {
            position: Position {
                id: pos.id,
                account_id: pos.account_id,
                ticker: pos.ticker.clone(),
                isin: pos.isin.clone(),
                name: pos.name.clone(),
                quantity: pos.quantity,
                avg_cost: pos.avg_cost,
                current_price: pos.current_price,
                currency: pos.currency.clone(),
                asset_type: pos.asset_type.clone(),
                sector: pos.sector.clone(),
                country: pos.country.clone(),
            },
            value_native,
            value_eur,
            pnl_native,
            pnl_eur,
            pnl_pct: pnl_pct.round_dp(2),
            weight_pct: Decimal::ZERO, // filled after total computed
        });
    }

    // Set weight percentages
    if total_eur > Decimal::ZERO {
        for v in &mut valuations {
            v.weight_pct = ((v.value_eur / total_eur) * Decimal::from(100)).round_dp(2);
        }
    }

    (valuations, total_eur)
}

/// Compute diversification score (0-100).
pub fn diversification_score(valuations: &[PositionValuation]) -> u32 {
    if valuations.is_empty() {
        return 0;
    }

    let mut score: f64 = 50.0; // baseline

    // Sector diversity
    let sectors: std::collections::HashSet<_> = valuations
        .iter()
        .filter_map(|v| v.position.sector.as_deref())
        .collect();
    score += (sectors.len() as f64).min(10.0) * 2.0;

    // Country diversity
    let countries: std::collections::HashSet<_> = valuations
        .iter()
        .filter_map(|v| v.position.country.as_deref())
        .collect();
    score += (countries.len() as f64).min(10.0) * 1.5;

    // Concentration penalty: if any position > 30% weight
    let max_weight = valuations
        .iter()
        .map(|v| v.weight_pct)
        .max()
        .unwrap_or(Decimal::ZERO);
    if max_weight > Decimal::from(30) {
        score -= 15.0;
    }
    if max_weight > Decimal::from(50) {
        score -= 15.0;
    }

    // Number of positions
    score += (valuations.len() as f64).min(20.0);

    score.clamp(0.0, 100.0) as u32
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

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    fn make_position(ticker: &str, qty: i64, cost: i64, price: i64, currency: &str, asset_type: &str) -> Position {
        Position {
            id: Uuid::new_v4(),
            account_id: None,
            ticker: ticker.to_string(),
            isin: None,
            name: ticker.to_string(),
            quantity: Decimal::from(qty),
            avg_cost: Some(Decimal::from(cost)),
            current_price: Some(Decimal::from(price)),
            currency: Some(currency.to_string()),
            asset_type: asset_type.to_string(),
            sector: Some("Technology".to_string()),
            country: Some("US".to_string()),
        }
    }

    fn test_rates() -> HashMap<String, Decimal> {
        let mut m = HashMap::new();
        m.insert("EUR".to_string(), Decimal::ONE);
        m.insert("USD".to_string(), Decimal::new(10380, 4)); // 1.0380
        m.insert("GBP".to_string(), Decimal::new(8340, 4)); // 0.8340
        m
    }

    #[test]
    fn test_value_eur_position() {
        let positions = vec![make_position("BNP.PA", 200, 52, 62, "EUR", "stock")];
        let (vals, total) = value_positions(&positions, &test_rates());

        assert_eq!(vals.len(), 1);
        assert_eq!(vals[0].value_native, Decimal::from(12400)); // 200 * 62
        assert_eq!(vals[0].value_eur, Decimal::from(12400)); // EUR → EUR
        assert_eq!(vals[0].pnl_native, Decimal::from(2000)); // (62-52)*200
        assert_eq!(total, Decimal::from(12400));
        assert_eq!(vals[0].weight_pct, Decimal::from(100)); // only position
    }

    #[test]
    fn test_value_usd_position() {
        let positions = vec![make_position("AAPL", 100, 180, 230, "USD", "stock")];
        let rates = test_rates();
        let (vals, total) = value_positions(&positions, &rates);

        // $23,000 / 1.0380 = €22,158.00
        assert_eq!(vals[0].value_native, Decimal::from(23000));
        let expected_eur = (Decimal::from(23000) / Decimal::new(10380, 4)).round_dp(2);
        assert_eq!(vals[0].value_eur, expected_eur);
        assert_eq!(total, expected_eur);
    }

    #[test]
    fn test_mixed_currency_weights_sum_100() {
        let positions = vec![
            make_position("AAPL", 100, 180, 230, "USD", "stock"),
            make_position("BNP.PA", 200, 52, 62, "EUR", "stock"),
        ];
        let (vals, _) = value_positions(&positions, &test_rates());
        let total_weight: Decimal = vals.iter().map(|v| v.weight_pct).sum();
        assert_eq!(total_weight, Decimal::from(100));
    }

    #[test]
    fn test_pnl_calculation() {
        let positions = vec![make_position("TEST", 10, 100, 150, "EUR", "stock")];
        let (vals, _) = value_positions(&positions, &test_rates());
        assert_eq!(vals[0].pnl_native, Decimal::from(500)); // (150-100)*10
        assert_eq!(vals[0].pnl_pct, Decimal::from(50)); // 500/1000 * 100
    }

    #[test]
    fn test_zero_cost_pnl() {
        let mut pos = make_position("TEST", 10, 0, 100, "EUR", "stock");
        pos.avg_cost = Some(Decimal::ZERO);
        let (vals, _) = value_positions(&[pos], &test_rates());
        assert_eq!(vals[0].pnl_pct, Decimal::ZERO);
    }

    #[test]
    fn test_empty_positions() {
        let (vals, total) = value_positions(&[], &test_rates());
        assert!(vals.is_empty());
        assert_eq!(total, Decimal::ZERO);
    }

    #[test]
    fn test_diversification_score_single() {
        let positions = vec![make_position("AAPL", 100, 180, 230, "USD", "stock")];
        let (vals, _) = value_positions(&positions, &test_rates());
        let score = diversification_score(&vals);
        // Single position → max_weight=100% → big penalty
        assert!(score < 60);
    }

    #[test]
    fn test_diversification_score_diverse() {
        let mut positions = Vec::new();
        for (i, sector) in ["Tech", "Finance", "Health", "Energy", "Consumer"].iter().enumerate() {
            let mut p = make_position(&format!("T{}", i), 10, 100, 100, "EUR", "stock");
            p.sector = Some(sector.to_string());
            p.country = Some(if i % 2 == 0 { "US" } else { "FR" }.to_string());
            positions.push(p);
        }
        let (vals, _) = value_positions(&positions, &test_rates());
        let score = diversification_score(&vals);
        assert!(score > 60);
    }
}
