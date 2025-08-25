"""Unit tests for database models and operations."""

import pytest
import json
from datetime import datetime, timedelta

from wins_finder.database.models import WinsDatabase


@pytest.mark.unit
class TestWinsDatabase:
    """Test database operations."""

    def test_database_initialization(self, temp_db):
        """Test database initialization."""
        assert temp_db is not None
        assert temp_db.engine is not None
        assert not temp_db._initialized

    def test_lazy_initialization(self, temp_db):
        """Test that tables are created on first use."""
        # Tables should be created when first accessed
        temp_db._ensure_initialized()
        assert temp_db._initialized

    def test_cache_activity_data(self, temp_db, sample_github_activity, date_range):
        """Test caching activity data."""
        start_date, end_date = date_range
        
        cache_id = temp_db.cache_activity_data(
            source="github",
            data_type="activity", 
            data=sample_github_activity,
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        assert isinstance(cache_id, int)
        assert cache_id > 0

    def test_get_cached_activity_hit(self, temp_db, sample_github_activity, date_range):
        """Test cache hit - data is returned."""
        start_date, end_date = date_range
        
        # Cache some data
        temp_db.cache_activity_data(
            source="github",
            data_type="activity",
            data=sample_github_activity,
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        # Retrieve cached data
        cached_data = temp_db.get_cached_activity(
            source="github",
            data_type="activity",
            timeframe_start=start_date,
            timeframe_end=end_date,
            max_age_hours=1
        )
        
        assert cached_data is not None
        assert cached_data["user"]["login"] == "testuser"
        assert len(cached_data["activities"]) == 3

    def test_get_cached_activity_miss(self, temp_db, date_range):
        """Test cache miss - no data returned."""
        start_date, end_date = date_range
        
        cached_data = temp_db.get_cached_activity(
            source="github",
            data_type="activity", 
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        assert cached_data is None

    def test_get_cached_activity_expired(self, temp_db, sample_github_activity, date_range):
        """Test cache expiry - old data not returned."""
        import json
        from datetime import datetime, timedelta
        from wins_finder.database.models import raw_activity
        
        start_date, end_date = date_range
        
        # Ensure database is initialized
        temp_db._ensure_initialized()
        
        # Manually insert old data with a timestamp in the past
        old_timestamp = datetime.now() - timedelta(hours=2)
        with temp_db.engine.connect() as conn:
            conn.execute(
                raw_activity.insert().values(
                    source="github",
                    data_type="activity",
                    data_json=json.dumps(sample_github_activity),
                    timeframe_start=start_date,
                    timeframe_end=end_date,
                    timestamp=old_timestamp
                )
            )
            conn.commit()
        
        # Try to retrieve with max_age of 1 hour (data is 2 hours old, should be expired)
        cached_data = temp_db.get_cached_activity(
            source="github",
            data_type="activity",
            timeframe_start=start_date,
            timeframe_end=end_date,
            max_age_hours=1  # Data older than 1 hour is expired
        )
        
        assert cached_data is None

    def test_save_and_get_preference(self, temp_db):
        """Test saving and retrieving preferences."""
        # Save a preference
        temp_db.save_preference("test_key", {"setting": "value", "number": 42})
        
        # Retrieve it
        value = temp_db.get_preference("test_key")
        assert value == {"setting": "value", "number": 42}

    def test_get_preference_default(self, temp_db):
        """Test getting preference with default value."""
        value = temp_db.get_preference("nonexistent_key", "default_value")
        assert value == "default_value"

    def test_update_preference(self, temp_db):
        """Test updating existing preference."""
        # Save initial preference
        temp_db.save_preference("update_key", "initial_value")
        
        # Update it
        temp_db.save_preference("update_key", "updated_value")
        
        # Check it was updated
        value = temp_db.get_preference("update_key")
        assert value == "updated_value"

    def test_save_wins(self, temp_db, sample_wins_data, date_range):
        """Test saving wins data."""
        start_date, _ = date_range
        
        wins_id = temp_db.save_wins(start_date, sample_wins_data)
        
        assert isinstance(wins_id, int)
        assert wins_id > 0

    def test_save_correlation(self, temp_db):
        """Test saving correlations."""
        related_events = [
            {"service": "github", "type": "pull_request", "id": "123"},
            {"service": "linear", "type": "issue", "id": "AUTH-45"},
        ]
        
        correlation_id = temp_db.save_correlation(
            primary_source="github",
            primary_id="123",
            related_events=related_events,
            confidence=0.85,
            correlation_type="feature_delivery"
        )
        
        assert isinstance(correlation_id, int)
        assert correlation_id > 0

    def test_get_cache_stats(self, temp_db, sample_github_activity, date_range):
        """Test getting cache statistics."""
        start_date, end_date = date_range
        
        # Add some cached data
        temp_db.cache_activity_data(
            source="github",
            data_type="prs",
            data=sample_github_activity,
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        temp_db.cache_activity_data(
            source="linear", 
            data_type="issues",
            data={"issues": []},
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        stats = temp_db.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert "github_prs" in stats
        assert "linear_issues" in stats
        assert stats["github_prs"]["count"] == 1
        assert stats["linear_issues"]["count"] == 1

    def test_clear_cache(self, temp_db, sample_github_activity, date_range):
        """Test clearing old cache data."""
        start_date, end_date = date_range
        
        # Add some cached data
        temp_db.cache_activity_data(
            source="github",
            data_type="activity",
            data=sample_github_activity,
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        # Verify it exists
        cached_data = temp_db.get_cached_activity(
            source="github",
            data_type="activity",
            timeframe_start=start_date, 
            timeframe_end=end_date
        )
        assert cached_data is not None
        
        # Clear cache (with days=-1 to clear everything including items from "now")
        temp_db.clear_cache(older_than_days=-1)
        
        # Verify it's gone
        cached_data = temp_db.get_cached_activity(
            source="github",
            data_type="activity",
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        assert cached_data is None