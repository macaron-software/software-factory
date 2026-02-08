---
name: mobile-finance
description: Native mobile patterns for personal finance apps. Use when building or modifying the iOS (SwiftUI) or Android (Jetpack Compose) clients. Covers net worth display, portfolio views, transaction lists, pull-to-refresh sync, biometric auth, and financial number formatting for FR locale.
---

# Mobile Finance

Patterns iOS (SwiftUI) et Android (Jetpack Compose) pour l'app finance.

## iOS — SwiftUI

### Architecture

```
ios/
├── FinaryApp.swift
├── Models/
│   ├── Account.swift
│   ├── Position.swift
│   ├── Transaction.swift
│   └── NetWorth.swift
├── ViewModels/
│   ├── DashboardViewModel.swift
│   ├── PortfolioViewModel.swift
│   └── AccountsViewModel.swift
├── Views/
│   ├── Dashboard/
│   │   ├── DashboardView.swift
│   │   ├── NetWorthCard.swift
│   │   └── AllocationChart.swift
│   ├── Portfolio/
│   │   ├── PortfolioView.swift
│   │   └── PositionRow.swift
│   ├── Accounts/
│   │   ├── AccountsView.swift
│   │   └── TransactionRow.swift
│   └── Components/
│       ├── AmountText.swift
│       ├── PnLBadge.swift
│       └── SparklineView.swift
├── Services/
│   ├── APIClient.swift
│   └── BiometricAuth.swift
└── Utils/
    └── Formatters.swift
```

### Formatage Montants (FR)

```swift
extension Decimal {
    func formatted(currency: String = "EUR") -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = currency
        formatter.locale = Locale(identifier: "fr_FR")
        return formatter.string(from: self as NSDecimalNumber) ?? "—"
    }
    
    func formattedPct() -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .percent
        formatter.minimumFractionDigits = 2
        formatter.multiplier = 1  // déjà en %
        return formatter.string(from: (self / 100) as NSDecimalNumber) ?? "—"
    }
}

// Couleur selon P&L
extension Color {
    static func pnl(_ value: Decimal) -> Color {
        value > 0 ? .green : value < 0 ? .red : .secondary
    }
}
```

### Pull-to-Refresh Sync

```swift
struct DashboardView: View {
    @StateObject var vm = DashboardViewModel()
    
    var body: some View {
        ScrollView {
            // ... content
        }
        .refreshable {
            await vm.triggerSync()
        }
    }
}
```

## Android — Jetpack Compose

### Architecture

```
android/
├── app/src/main/java/com/finary/
│   ├── FinaryApp.kt
│   ├── data/
│   │   ├── api/FinaryApi.kt
│   │   ├── model/
│   │   └── repository/
│   ├── ui/
│   │   ├── dashboard/
│   │   ├── portfolio/
│   │   ├── accounts/
│   │   └── components/
│   └── di/AppModule.kt
```

### Formatage (FR)

```kotlin
fun Decimal.formatCurrency(currency: String = "EUR"): String {
    val format = NumberFormat.getCurrencyInstance(Locale.FRANCE)
    format.currency = Currency.getInstance(currency)
    return format.format(this)
}

@Composable
fun AmountText(amount: BigDecimal, modifier: Modifier = Modifier) {
    val color = when {
        amount > BigDecimal.ZERO -> Color(0xFF10B981)
        amount < BigDecimal.ZERO -> Color(0xFFEF4444)
        else -> MaterialTheme.colorScheme.onSurface
    }
    Text(
        text = amount.formatCurrency(),
        color = color,
        style = MaterialTheme.typography.titleMedium,
        modifier = modifier,
    )
}
```

## Patterns Communs

- **Biometric auth** : Face ID / Touch ID (iOS) et BiometricPrompt (Android) au lancement
- **Pull-to-refresh** : Trigger sync manuelle
- **Offline cache** : Données en cache local (Core Data / Room)
- **Notifications** : Alertes dividendes, variations importantes, sync errors
- **Locale** : FR par défaut, formatage nombres/dates français
