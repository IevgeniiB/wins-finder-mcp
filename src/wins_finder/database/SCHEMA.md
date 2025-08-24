# Database Schema Documentation

This document describes the database schema for the Wins Finder MCP Agent, built using SQLAlchemy Core with SQLite.

## Overview

The Wins Finder database consists of four main tables designed to support intelligent activity analysis, caching, learning, and cross-service correlation discovery.

## Tables

### `raw_activity`
**Purpose**: Cache API responses from external services to avoid rate limits and enable offline analysis.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key, Auto-increment | Unique identifier for each cached response |
| `source` | String(50) | Not Null | Service source: `'github'`, `'linear'`, `'notion'`, `'slack'` |
| `data_type` | String(50) | Not Null | Type of data: `'prs'`, `'issues'`, `'pages'`, `'messages'` |
| `timestamp` | DateTime | Not Null, Default: now() | When the data was cached |
| `timeframe_start` | DateTime | Not Null | Start of the activity timeframe queried |
| `timeframe_end` | DateTime | Not Null | End of the activity timeframe queried |
| `data_json` | Text | Not Null | Raw JSON response from the API |
| `processed` | Boolean | Default: False | Whether this data has been analyzed |

**Usage Examples**:
```python
# Cache GitHub PR data for last week
db.cache_activity_data(
    source="github", 
    data_type="prs",
    data=github_prs_response,
    timeframe_start=datetime(2024, 1, 15),
    timeframe_end=datetime(2024, 1, 22)
)

# Retrieve cached data if still fresh (within 6 hours)
cached_data = db.get_cached_activity(
    source="github",
    data_type="prs", 
    timeframe_start=datetime(2024, 1, 15),
    timeframe_end=datetime(2024, 1, 22),
    max_age_hours=6
)
```

### `user_preferences`
**Purpose**: Store user settings and learned preferences to personalize analysis and report generation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `key` | String(100) | Primary Key | Unique preference key |
| `value` | Text | Not Null | JSON-encoded preference value |
| `updated_at` | DateTime | Not Null, Default: now() | Last update timestamp |

**Usage Examples**:
```python
# Save user's preferred audience
db.save_preference("default_audience", "manager")

# Save focus areas
db.save_preference("focus_areas", ["technical", "leadership", "collaboration"])

# Save report format preference
db.save_preference("report_format", "markdown")

# Retrieve preferences
audience = db.get_preference("default_audience", default="self")
focus_areas = db.get_preference("focus_areas", default=[])
```

### `wins_history`
**Purpose**: Store historical wins reports for pattern learning and effectiveness tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key, Auto-increment | Unique identifier for each wins report |
| `week_start` | DateTime | Not Null | Monday of the week being analyzed |
| `win_data_json` | Text | Not Null | Complete wins analysis data as JSON |
| `feedback_json` | Text | Nullable | User feedback on report effectiveness |
| `effectiveness_score` | Float | Nullable | Calculated effectiveness score (0.0-1.0) |
| `created_at` | DateTime | Not Null, Default: now() | When the report was generated |

**Usage Examples**:
```python
# Save a weekly wins report
week_start = datetime(2024, 1, 15)  # Monday
wins_data = {
    "summary": {"total_activities": 25},
    "categories": [...],
    "correlations": [...]
}
report_id = db.save_wins(week_start, wins_data)

# Later, store user feedback
feedback = {"rating": 4, "comments": "Good technical detail"}
db.save_wins_feedback(report_id, feedback, effectiveness_score=0.8)
```

### `correlations`
**Purpose**: Store discovered cross-service correlations for reuse and pattern recognition.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | Primary Key, Auto-increment | Unique identifier for each correlation |
| `primary_event_source` | String(50) | Not Null | Source of the primary event (`'github'`, `'linear'`, etc.) |
| `primary_event_id` | String(200) | Not Null | Unique identifier of the primary event |
| `related_events_json` | Text | Not Null | JSON array of related events across services |
| `confidence_score` | Float | Not Null | Confidence level (0.0-1.0) of the correlation |
| `correlation_type` | String(100) | Not Null | Type: `'temporal'`, `'keyword'`, `'semantic'`, `'causal'` |
| `created_at` | DateTime | Not Null, Default: now() | When the correlation was discovered |

**Usage Examples**:
```python
# Save a cross-service correlation
related_events = [
    {"service": "github", "type": "pull_request", "id": "12345", "title": "Add user auth"},
    {"service": "linear", "type": "issue", "id": "AUTH-123", "title": "Implement authentication"},
    {"service": "notion", "type": "page", "id": "abc123", "title": "Auth Architecture Doc"}
]

correlation_id = db.save_correlation(
    primary_source="github",
    primary_id="12345", 
    related_events=related_events,
    confidence=0.9,
    correlation_type="semantic"
)

# Query correlations for a specific event
correlations = db.get_correlations_for_event("github", "12345")
```

## Data Flow

1. **Collection**: External API data flows into `raw_activity` table via caching
2. **Analysis**: LLM processes cached data to discover correlations, stored in `correlations` table
3. **Generation**: Wins reports generated from correlations and activities, stored in `wins_history`
4. **Learning**: User feedback and preferences stored in `user_preferences` for future personalization

## Database Lifecycle

- **Initialization**: Tables created automatically on first use via lazy initialization
- **Caching**: Data cached with TTL to balance freshness vs API limits
- **Cleanup**: Old cache entries removed via `clear_cache()` method (default: 7 days)
- **Growth**: Database grows with user activity but remains lightweight for personal use

## Performance Considerations

- **Indexes**: Implicit indexes on primary keys and datetime columns for efficient querying
- **JSON Storage**: Flexible schema using JSON columns for complex data structures
- **Cache Strategy**: Time-based cache invalidation prevents stale data while reducing API calls
- **Cleanup**: Regular cleanup prevents unbounded growth

## Security Notes

- **No Credentials**: API keys and tokens are NEVER stored in database
- **Local Storage**: Database stored in user data directory with appropriate permissions
- **Data Privacy**: All data remains local, no external transmission of cached activity data