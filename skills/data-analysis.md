---
name: data-analysis
description: >
  Guides the agent through data analysis tasks including SQL queries, data exploration,
  dashboard design, KPI definition, statistical basics, data visualization, and ETL
  patterns. Use this skill when working with data, building reports, or designing
  analytics features.
metadata:
  category: development
  triggers:
    - "when user asks to write SQL queries"
    - "when exploring or analyzing data"
    - "when designing dashboards or reports"
    - "when defining KPIs or metrics"
    - "when building ETL pipelines"
    - "when user asks about data visualization"
---

# Data Analysis

This skill enables the agent to perform data analysis tasks — SQL queries, data exploration,
dashboard design, KPI definition, and ETL patterns.

## Use this skill when

- Writing SQL queries for reports or analysis
- Exploring datasets to find patterns
- Designing dashboards and visualizations
- Defining KPIs and metrics
- Building ETL (Extract, Transform, Load) pipelines
- Performing basic statistical analysis

## Do not use this skill when

- Building application features (use development skills)
- Doing security reviews (use security-audit)
- Managing projects (use project-management)

## Instructions

### SQL Query Patterns

#### Aggregation with Grouping

```sql
-- Daily active users over the last 30 days
SELECT
    DATE(created_at) AS date,
    COUNT(DISTINCT user_id) AS daily_active_users,
    COUNT(*) AS total_events
FROM events
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date;
```

#### Window Functions

```sql
-- Running total and rank by category
SELECT
    category,
    product_name,
    revenue,
    SUM(revenue) OVER (PARTITION BY category ORDER BY revenue DESC) AS running_total,
    RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rank_in_category
FROM sales
WHERE sale_date >= '2024-01-01';
```

#### Cohort Analysis

```sql
-- Monthly retention cohort
WITH user_cohorts AS (
    SELECT
        user_id,
        DATE_TRUNC('month', MIN(created_at)) AS cohort_month
    FROM users
    GROUP BY user_id
),
user_activity AS (
    SELECT
        e.user_id,
        DATE_TRUNC('month', e.created_at) AS activity_month
    FROM events e
    GROUP BY e.user_id, DATE_TRUNC('month', e.created_at)
)
SELECT
    uc.cohort_month,
    ua.activity_month,
    COUNT(DISTINCT ua.user_id) AS active_users,
    ROUND(
        COUNT(DISTINCT ua.user_id)::numeric /
        (SELECT COUNT(DISTINCT user_id) FROM user_cohorts WHERE cohort_month = uc.cohort_month) * 100,
        1
    ) AS retention_pct
FROM user_cohorts uc
JOIN user_activity ua ON uc.user_id = ua.user_id
WHERE ua.activity_month >= uc.cohort_month
GROUP BY uc.cohort_month, ua.activity_month
ORDER BY uc.cohort_month, ua.activity_month;
```

#### Funnel Analysis

```sql
-- Conversion funnel
WITH funnel AS (
    SELECT
        COUNT(DISTINCT CASE WHEN event = 'page_view' THEN user_id END) AS step_1_views,
        COUNT(DISTINCT CASE WHEN event = 'add_to_cart' THEN user_id END) AS step_2_cart,
        COUNT(DISTINCT CASE WHEN event = 'checkout_start' THEN user_id END) AS step_3_checkout,
        COUNT(DISTINCT CASE WHEN event = 'purchase' THEN user_id END) AS step_4_purchase
    FROM events
    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
)
SELECT
    step_1_views AS "Page Views",
    step_2_cart AS "Add to Cart",
    ROUND(step_2_cart::numeric / NULLIF(step_1_views, 0) * 100, 1) AS "View→Cart %",
    step_3_checkout AS "Checkout Start",
    ROUND(step_3_checkout::numeric / NULLIF(step_2_cart, 0) * 100, 1) AS "Cart→Checkout %",
    step_4_purchase AS "Purchase",
    ROUND(step_4_purchase::numeric / NULLIF(step_1_views, 0) * 100, 1) AS "Overall Conv %"
FROM funnel;
```

### KPI Definition Framework

| Category | KPI | Formula | Good Target |
|----------|-----|---------|-------------|
| Growth | DAU | Distinct users/day | Trending up |
| Growth | MAU | Distinct users/month | Trending up |
| Growth | DAU/MAU | DAU ÷ MAU | > 20% (stickiness) |
| Revenue | MRR | Sum of monthly recurring | Trending up |
| Revenue | ARPU | Revenue ÷ Active Users | Trending up |
| Retention | D1/D7/D30 | Users returning after N days | D1>40%, D7>20%, D30>10% |
| Engagement | Session length | Avg time per session | Depends on product |
| Quality | Error rate | Errors ÷ Total requests | < 0.1% |
| Quality | P95 latency | 95th percentile response time | < 500ms |

### Dashboard Design Principles

1. **One primary metric per dashboard** — What's the ONE number that matters?
2. **Comparison context** — Show current vs. previous period (WoW, MoM)
3. **Hierarchy** — Most important metric largest and top-left
4. **Actionable** — Every chart should answer a question that leads to action
5. **No vanity metrics** — If you can't act on it, don't show it

```
Dashboard Layout:
┌─────────────────────────────────────────────┐
│  KPI Cards (top row)                         │
│  [DAU: 1,234 ↑12%] [Revenue: $45K ↑5%]     │
│  [Conv: 3.2% ↓0.1%] [Error: 0.02% ✅]      │
├─────────────────────────────────────────────┤
│  Main Chart (trend over time)                │
│  [Line chart: DAU over last 30 days]         │
├──────────────────────┬──────────────────────┤
│  Breakdown Chart     │  Table/List           │
│  [Bar: by channel]   │  [Top pages/products] │
└──────────────────────┴──────────────────────┘
```

### Data Visualization Best Practices

| Data Type | Best Chart | Avoid |
|-----------|-----------|-------|
| Trend over time | Line chart | Pie chart |
| Part of whole | Stacked bar, treemap | Pie chart (>5 slices) |
| Comparison | Bar chart (horizontal) | 3D bars |
| Distribution | Histogram, box plot | Pie chart |
| Correlation | Scatter plot | Line chart |
| Geographic | Choropleth map | Bar chart |

### ETL Patterns

```python
# Simple ETL pipeline
import pandas as pd
from datetime import datetime, timedelta

def extract(source_db, query: str) -> pd.DataFrame:
    """Extract data from source database."""
    return pd.read_sql(query, source_db)

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and transform raw data."""
    # Remove duplicates
    df = df.drop_duplicates(subset=['id'])

    # Handle missing values
    df['email'] = df['email'].fillna('unknown')
    df['amount'] = df['amount'].fillna(0)

    # Type conversion
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['amount'] = df['amount'].astype(float)

    # Derived columns
    df['month'] = df['created_at'].dt.to_period('M')
    df['is_high_value'] = df['amount'] > 100

    # Filter invalid records
    df = df[df['amount'] >= 0]

    return df

def load(df: pd.DataFrame, target_db, table: str):
    """Load transformed data into target."""
    df.to_sql(table, target_db, if_exists='append', index=False)

# Run pipeline
raw_data = extract(source, "SELECT * FROM orders WHERE date >= %(start)s")
cleaned = transform(raw_data)
load(cleaned, warehouse, 'fact_orders')
```

### Statistical Basics

```python
import numpy as np

# Descriptive statistics
data = [values]
mean = np.mean(data)
median = np.median(data)
std_dev = np.std(data)
percentile_95 = np.percentile(data, 95)

# A/B test significance (simplified)
from scipy import stats

control = [conversion_rates_control]
variant = [conversion_rates_variant]
t_stat, p_value = stats.ttest_ind(control, variant)
significant = p_value < 0.05  # 95% confidence
```

## Output Format

```
## Data Analysis: [Question/Topic]

### Query
[SQL or code used]

### Results Summary
[Key findings in 2-3 bullet points]

### Visualization
[Description or ASCII representation of recommended chart]

### Recommendations
[Data-driven recommendations based on findings]
```

## Anti-patterns

- **NEVER** use SELECT * in production queries — specify columns
- **NEVER** skip LIMIT on exploratory queries — protect the database
- **NEVER** join without indexes — check query plans
- **NEVER** use pie charts for more than 5 categories
- **NEVER** show raw numbers without context (comparison, trend)
- **NEVER** use averages alone — show medians and percentiles too
- **NEVER** draw conclusions from too-small sample sizes
- **NEVER** build dashboards without asking "what decision does this help make?"
