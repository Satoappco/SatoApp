# Metrics Sync with Gap Detection

## Overview

The `/campaign-sync/sync-metrics` endpoint now intelligently detects and fills gaps in historical metrics data. Instead of blindly syncing the last N days, it checks which days are missing for each ad/ad_group and only fetches the necessary data.

**Created:** 2025-11-24
**Status:** ✅ Implemented

---

## How It Works

### 1. Gap Detection

For each advertising platform (Google Ads, Facebook Ads):

1. **Find all unique ads/ad_groups** that have existing metrics in the database
2. **Check the past 90 days** for each ad/ad_group
3. **Identify missing dates** where no metrics exist
4. **Always include yesterday and today** in the sync (even if they exist)

### 2. Efficient Fetching

Instead of making individual API calls for each missing date:

- **Google Ads**: Uses `BETWEEN` clause to fetch all dates in a single query
- **Facebook Ads**: Uses `time_increment=1` with date range to get daily breakdowns

### 3. Upsert Strategy

- Uses PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE`
- Ensures yesterday and today are always refreshed with latest data
- No duplicate records thanks to unique constraint on `(metric_date, item_id, platform_id)`

---

## Benefits

### 1. Data Completeness

✅ **Before**: Missing data if sync failed or was skipped
✅ **After**: Automatically detects and fills all gaps in the past 90 days

### 2. Cost Efficiency

✅ **Before**: Re-fetched all 90 days even if most data existed
✅ **After**: Only fetches missing dates, reducing API calls and processing time

### 3. Data Freshness

✅ **Before**: Yesterday might not be updated if sync ran early
✅ **After**: Always refreshes yesterday and today to ensure latest data

### 4. New Ad Handling

✅ **Before**: New ads had no historical data
✅ **After**: Automatically backfills all 90 days for new ads

---

## Implementation Details

### Helper Method: `_get_dates_to_sync`

Located in `app/services/campaign_sync_service.py`

```python
def _get_dates_to_sync(self, session: Session, platform_id: int) -> List[date]:
    """
    Get list of dates to sync for a platform.

    Returns dates that:
    1. Are missing for any ad/ad_group in the past 90 days
    2. Always includes yesterday and today
    """
```

**Logic:**

```python
# 1. Get all unique ads/ad_groups for this platform
all_items = session.exec(
    select(Metrics.item_id).where(
        Metrics.platform_id == platform_id
    ).distinct()
).all()

# 2. For each ad/ad_group, find missing dates
for item_id in all_items:
    existing_dates = session.exec(
        select(Metrics.metric_date).where(
            Metrics.platform_id == platform_id,
            Metrics.item_id == item_id,
            Metrics.metric_date >= start_date  # Past 90 days
        )
    ).all()

    # Find missing dates
    all_dates = {start_date + timedelta(days=i) for i in range(91)}
    missing_for_item = all_dates - existing_dates_set
    missing_dates_set.update(missing_for_item)

# 3. Always include yesterday and today
dates_to_sync = missing_dates_set | {yesterday, today}
```

### Updated Methods

#### Google Ads: `_sync_google_ads_metrics`

**Signature Change:**
```python
# Before
def _sync_google_ads_metrics(
    self, session, platform, connection, sync_date: date
) -> int:

# After
def _sync_google_ads_metrics(
    self, session, platform, connection, sync_dates: List[date]
) -> int:
```

**Query Update:**
```sql
-- Before (single date)
WHERE segments.date = '2025-11-23'

-- After (date range)
WHERE segments.date BETWEEN '2025-08-25' AND '2025-11-24'
```

**Date Filtering:**
```python
# Parse date from row
metric_date_str = row.segments.date  # 'YYYY-MM-DD'
year, month, day = map(int, metric_date_str.split('-'))
metric_date = date(year, month, day)

# Skip if not in our sync list
if metric_date not in sync_dates_set:
    continue
```

#### Facebook Ads: `_sync_facebook_metrics`

**Signature Change:**
```python
# Before
def _sync_facebook_metrics(
    self, session, platform, connection, sync_date: date
) -> int:

# After
def _sync_facebook_metrics(
    self, session, platform, connection, sync_dates: List[date]
) -> int:
```

**API Call Update:**
```python
# Before (single date)
params = {
    'time_range': json.dumps({
        'since': '2025-11-23',
        'until': '2025-11-23'
    })
}

# After (date range with daily breakdowns)
params = {
    'time_range': json.dumps({
        'since': '2025-08-25',
        'until': '2025-11-24'
    }),
    'time_increment': 1,  # Daily breakdowns
    'fields': 'ad_id,ad_name,date_start,date_stop,...'
}
```

**Date Filtering:**
```python
# Parse date from insight
date_start_str = insight.get('date_start')  # 'YYYY-MM-DD'
year, month, day = map(int, date_start_str.split('-'))
metric_date = date(year, month, day)

# Skip if not in our sync list
if metric_date not in sync_dates_set:
    continue
```

---

## Usage

### Manual Sync (All Customers)

```bash
POST /api/v1/campaign-sync/sync-metrics
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Metrics sync completed by user@example.com",
  "customers_processed": 5,
  "platforms_processed": 10,
  "metrics_upserted": 1250,
  "errors_count": 0,
  "connection_failures": 0,
  "error_details": [],
  "duration_seconds": 45.32
}
```

### Manual Sync (Specific Customer)

```bash
POST /api/v1/campaign-sync/sync-metrics?customer_id=123
Authorization: Bearer <token>
```

---

## Examples

### Example 1: New Platform with No Data

**Scenario:** User connects a new Google Ads account

**Behavior:**
1. No existing metrics found
2. Syncs all 90 days: `2025-08-25` to `2025-11-24`
3. Creates ~90 metric records per ad

**Log Output:**
```
📊 Processing customer: Acme Corp (ID: 123)
  📱 Found 1 platform(s)
  🔄 Syncing platform: Google Ads - Main Account
  ✅ Found working connection
  📅 No existing metrics found. Will sync all 90 days
  📊 Fetching Google Ads metrics for 91 dates (2025-08-25 to 2025-11-24)...
  ✅ Synced 910 Google Ads metrics for 91 dates
```

### Example 2: Existing Platform with Gaps

**Scenario:** Sync failed for 5 days, now running again

**Existing Data:**
- Ad 123: Has data for all days except Oct 10, Oct 11, Oct 12
- Ad 456: Has data for all days except Oct 10, Oct 15

**Behavior:**
1. Detects 4 unique missing dates: Oct 10, Oct 11, Oct 12, Oct 15
2. Always adds yesterday and today
3. Syncs 6 total dates (4 missing + yesterday + today)

**Log Output:**
```
📊 Found 2 unique ads/ad_groups
  Item 123: 3 missing dates
  Item 456: 2 missing dates
📅 Will sync 6 dates (4 missing + yesterday/today)
📊 Fetching Google Ads metrics for 6 dates (2025-10-10 to 2025-11-24)...
✅ Synced 12 Google Ads metrics for 6 dates
```

### Example 3: Fully Up-to-Date Platform

**Scenario:** All data exists for the past 90 days

**Behavior:**
1. No missing dates found
2. Only syncs yesterday and today (2 dates)
3. Updates existing records with latest data

**Log Output:**
```
📊 Found 10 unique ads/ad_groups
📅 Will sync 2 dates (0 missing + yesterday/today)
📊 Fetching Google Ads metrics for 2 dates (2025-11-23 to 2025-11-24)...
✅ Synced 20 Google Ads metrics for 2 dates
```

### Example 4: New Ad Appears

**Scenario:** User creates a new ad today

**Existing Data:**
- Old ads: Have full 90 days of data
- New ad: No data yet

**Behavior:**
1. New ad appears in API results but not in database
2. After first sync, new ad is in database with today's data
3. Next sync detects 89 missing days for the new ad
4. Backfills all 90 days for the new ad

**Log Output (First Sync):**
```
📅 No existing metrics found. Will sync all 90 days
```

**Log Output (Second Sync):**
```
📊 Found 11 unique ads/ad_groups
  Item 789: 89 missing dates
📅 Will sync 91 dates (89 missing + yesterday/today)
```

---

## Performance Considerations

### Query Optimization

**Database Queries:**
- Uses `DISTINCT` to find unique ads efficiently
- Filters by `metric_date >= start_date` using indexed column
- Result set size: O(ads × days) but typically small (100s of ads × 90 days)

**API Calls:**
- Single API call per platform (vs. one per date before)
- Date range queries are more efficient than individual date queries
- Reduces API quota usage significantly

### Memory Usage

**Small Overhead:**
- Stores date sets in memory: ~90 dates × 8 bytes = 720 bytes
- Stores ad IDs in set: ~100 ads × 50 bytes = 5 KB
- Total overhead per platform: < 10 KB

### Time Complexity

**Per Platform:**
1. Find unique ads: O(n) where n = existing metrics
2. Check dates per ad: O(m × 90) where m = number of ads
3. API fetch: O(ads × dates returned)
4. Upsert: O(p) where p = records to upsert

**Total:** O(n + m × 90 + p) ≈ O(n + p) for typical cases

---

## Monitoring

### Success Metrics

Monitor these fields in the response:

```python
{
    "metrics_upserted": 1250,      # How many records inserted/updated
    "errors_count": 0,              # Any errors during sync
    "connection_failures": 0,       # Platforms with no working connection
    "duration_seconds": 45.32       # Time taken
}
```

### Expected Behavior

| Scenario | metrics_upserted | duration_seconds |
|----------|------------------|------------------|
| First sync (new platform) | ~90 per ad | 30-60s per platform |
| Daily sync (no gaps) | ~2 per ad | 5-15s per platform |
| Sync after 7-day gap | ~9 per ad | 10-20s per platform |
| Sync after 30-day gap | ~32 per ad | 15-30s per platform |

### Warning Signs

🚨 **Connection Failures > 0**
- Action: Check OAuth tokens, re-authenticate users
- Auto-creates ClickUp bugs for investigation

🚨 **errors_count > 0**
- Action: Check error_details for specifics
- Common causes: API rate limits, token expiration, invalid ad IDs

🚨 **metrics_upserted = 0** (when it shouldn't be)
- Action: Check if ads are active and generating impressions
- May be normal if all ads are paused

---

## Database Schema

### Metrics Table

```sql
CREATE TABLE metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    item_id VARCHAR(100) NOT NULL,
    platform_id INTEGER NOT NULL REFERENCES digital_assets(id),
    item_type VARCHAR(20) NOT NULL,

    -- Performance metrics
    cpa DOUBLE PRECISION,
    cvr DOUBLE PRECISION,
    conv_val DOUBLE PRECISION,
    ctr DOUBLE PRECISION,
    cpc DOUBLE PRECISION,
    clicks INTEGER,
    cpm DOUBLE PRECISION,
    impressions INTEGER,
    reach INTEGER,
    frequency DOUBLE PRECISION,
    cpl DOUBLE PRECISION,
    leads INTEGER,
    spent DOUBLE PRECISION,
    conversions INTEGER,

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Unique constraint prevents duplicates
    CONSTRAINT uq_metrics_date_item_platform
        UNIQUE (metric_date, item_id, platform_id)
);

-- Indexes for efficient querying
CREATE INDEX idx_metrics_date ON metrics(metric_date);
CREATE INDEX idx_metrics_item_id ON metrics(item_id);
CREATE INDEX idx_metrics_platform_id ON metrics(platform_id);
CREATE INDEX idx_metrics_date_platform ON metrics(metric_date, platform_id);
```

### Data Retention

- Metrics older than 90 days are automatically deleted during sync
- Keeps database size manageable
- 90-day window is sufficient for most analysis and reporting needs

---

## Troubleshooting

### Issue: Sync says "0 dates to sync" but data is missing

**Cause:** The ad/ad_group may not exist in the metrics table yet

**Solution:**
1. Check if the ad is actually active and generating impressions
2. Verify the ad exists in the platform (Google Ads / Facebook Ads)
3. Try running sync again - first sync will detect it as "new" and backfill

### Issue: Some days are always missing

**Cause:** Ads may have been paused on those days (no impressions = no metrics)

**Solution:**
- This is normal - platforms don't return data for days with zero activity
- Gap detection will keep trying, but if ad had no impressions, no data exists

### Issue: Yesterday/today not updating

**Cause:** API call might be failing silently

**Solution:**
1. Check error_details in response
2. Verify connection is not expired
3. Check platform API status (Google Ads / Facebook Ads)

### Issue: Very slow sync (> 2 minutes per platform)

**Cause:** Too many ads or too many gaps to fill

**Solution:**
- Check metrics_upserted count - is it unusually high?
- Consider if all those ads are still active
- May need to archive old campaigns

---

## Related Documentation

- [Campaign Sync Service](./CAMPAIGN_SYNC_SERVICE.md) - Main sync service docs
- [Metrics Model](../app/models/analytics.py) - Database schema
- [API Routes](../app/api/v1/routes/campaign_sync.py) - API endpoints

---

## Future Enhancements

Potential improvements:

1. **Parallel Processing**: Sync multiple platforms concurrently
2. **Incremental Backfill**: Spread large backfills across multiple sync runs
3. **Smart Scheduling**: Adjust sync frequency based on ad activity
4. **Anomaly Detection**: Alert on unusual gaps or data patterns
5. **Compression**: Archive old metrics instead of deleting
