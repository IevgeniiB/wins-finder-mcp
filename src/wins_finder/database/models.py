"""SQLAlchemy Core models for the Wins Finder MCP agent."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import (
    MetaData, Table, Column, Integer, String, DateTime, Boolean, Float, Text,
    create_engine, select, insert, update, delete, func
)
from sqlalchemy.sql import text


metadata = MetaData()

# Cache API responses to avoid rate limits
raw_activity = Table(
    'raw_activity', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('source', String(50), nullable=False),  # 'github', 'linear', 'notion', 'slack'
    Column('data_type', String(50), nullable=False),  # 'prs', 'issues', 'pages', 'messages'
    Column('timestamp', DateTime, default=func.now(), nullable=False),
    Column('timeframe_start', DateTime, nullable=False),
    Column('timeframe_end', DateTime, nullable=False),
    Column('data_json', Text, nullable=False),
    Column('processed', Boolean, default=False),
)

# User preferences and learning
user_preferences = Table(
    'user_preferences', metadata,
    Column('key', String(100), primary_key=True),
    Column('value', Text, nullable=False),
    Column('updated_at', DateTime, default=func.now(), nullable=False),
)

# Historical wins for pattern learning
wins_history = Table(
    'wins_history', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('week_start', DateTime, nullable=False),
    Column('win_data_json', Text, nullable=False),
    Column('feedback_json', Text),
    Column('effectiveness_score', Float),
    Column('created_at', DateTime, default=func.now(), nullable=False),
)

# Cross-service correlations for reuse
correlations = Table(
    'correlations', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('primary_event_source', String(50), nullable=False),
    Column('primary_event_id', String(200), nullable=False),
    Column('related_events_json', Text, nullable=False),
    Column('confidence_score', Float, nullable=False),
    Column('correlation_type', String(100), nullable=False),
    Column('created_at', DateTime, default=func.now(), nullable=False),
)


class WinsDatabase:
    """SQLAlchemy Core database manager for the Wins Finder MCP agent."""
    
    def __init__(self, db_url: str = None):
        if db_url is None:
            # Use user data directory that's writable (macOS/Linux)
            try:
                data_dir = Path.home() / ".local" / "share" / "wins-finder"
                
                data_dir.mkdir(parents=True, exist_ok=True)
                db_path = data_dir / "wins_finder.db"
                db_url = f"sqlite:///{db_path}"
            except (OSError, PermissionError):
                # Fallback to temp directory if user data dir fails
                temp_dir = Path(tempfile.gettempdir()) / "wins-finder"
                temp_dir.mkdir(exist_ok=True)
                db_path = temp_dir / "wins_finder.db"
                db_url = f"sqlite:///{db_path}"
        
        self.engine = create_engine(db_url)
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of database tables."""
        if not self._initialized:
            # Create tables if they don't exist
            metadata.create_all(self.engine)
            self._initialized = True
    
    def cache_activity_data(
        self, 
        source: str, 
        data_type: str, 
        data: Dict[str, Any], 
        timeframe_start: datetime,
        timeframe_end: datetime
    ) -> int:
        """Cache API response data to avoid rate limits and enable offline analysis.
        
        This method stores raw API responses from external services with associated metadata
        to enable intelligent caching strategies. The cached data can be retrieved later
        based on service, data type, and timeframe matching.
        
        Args:
            source: Service identifier ('github', 'linear', 'notion', 'slack')
            data_type: Type of data being cached ('prs', 'issues', 'pages', 'messages')
            data: Raw API response data to cache (will be JSON-serialized)
            timeframe_start: Start of the queried time period
            timeframe_end: End of the queried time period
            
        Returns:
            Integer ID of the created cache entry for tracking purposes
            
        Example:
            cache_id = db.cache_activity_data(
                source="github",
                data_type="prs", 
                data={"pull_requests": [...]},
                timeframe_start=datetime(2024, 1, 15),
                timeframe_end=datetime(2024, 1, 22)
            )
        """
        self._ensure_initialized()
        with self.engine.connect() as conn:
            result = conn.execute(
                insert(raw_activity).values(
                    source=source,
                    data_type=data_type,
                    timeframe_start=timeframe_start,
                    timeframe_end=timeframe_end,
                    data_json=json.dumps(data)
                )
            )
            conn.commit()
            return result.inserted_primary_key[0]
    
    def get_cached_activity(
        self, 
        source: str, 
        data_type: str, 
        timeframe_start: datetime,
        timeframe_end: datetime,
        max_age_hours: int = 6
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached activity data if still fresh to avoid redundant API calls.
        
        This method implements intelligent cache retrieval based on exact timeframe matching
        and configurable freshness criteria. It helps reduce API rate limit consumption
        and enables faster response times for recent queries.
        
        Args:
            source: Service identifier ('github', 'linear', 'notion', 'slack')
            data_type: Type of data to retrieve ('prs', 'issues', 'pages', 'messages')
            timeframe_start: Start of the desired time period (must match exactly)
            timeframe_end: End of the desired time period (must match exactly)
            max_age_hours: Maximum age in hours for cache to be considered fresh (default: 6)
            
        Returns:
            Dictionary containing the cached API response data, or None if no fresh cache exists
            
        Example:
            cached_prs = db.get_cached_activity(
                source="github",
                data_type="prs",
                timeframe_start=datetime(2024, 1, 15),
                timeframe_end=datetime(2024, 1, 22),
                max_age_hours=6
            )
            if cached_prs is None:
                # Cache miss or expired, fetch from API
                fresh_data = github_client.fetch_prs(start, end)
        """
        self._ensure_initialized()
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.engine.connect() as conn:
            result = conn.execute(
                select(raw_activity.c.data_json)
                .where(
                    (raw_activity.c.source == source) &
                    (raw_activity.c.data_type == data_type) &
                    (raw_activity.c.timeframe_start == timeframe_start) &
                    (raw_activity.c.timeframe_end == timeframe_end) &
                    (raw_activity.c.timestamp > cutoff)
                )
                .order_by(raw_activity.c.timestamp.desc())
                .limit(1)
            )
            
            row = result.fetchone()
            if row:
                return json.loads(row.data_json)
        return None
    
    def save_preference(self, key: str, value: Any):
        """Save user preference to enable personalized analysis and report generation.
        
        This method stores user settings and learned preferences that influence how the agent
        analyzes activity and generates reports. Preferences are persisted across sessions
        and can be updated at any time to refine the user experience.
        
        Args:
            key: Unique preference identifier (e.g., 'default_audience', 'focus_areas')
            value: Preference value (will be JSON-serialized, so must be JSON-compatible)
            
        Common preference keys:
            - 'default_audience': Default target audience for reports ('self', 'manager', 'peer')
            - 'focus_areas': List of areas to emphasize (['technical', 'leadership', 'collaboration'])
            - 'report_format': Preferred output format ('markdown', 'json', 'slack')
            - 'tone_preference': Report tone ('professional', 'casual', 'detailed')
            
        Example:
            db.save_preference('default_audience', 'manager')
            db.save_preference('focus_areas', ['technical', 'collaboration'])
        """
        self._ensure_initialized()
        with self.engine.connect() as conn:
            # Check if exists, then update or insert
            existing = conn.execute(
                select(user_preferences.c.key).where(user_preferences.c.key == key)
            ).fetchone()
            
            if existing:
                # Update existing
                conn.execute(
                    update(user_preferences)
                    .where(user_preferences.c.key == key)
                    .values(value=json.dumps(value), updated_at=func.now())
                )
            else:
                # Insert new
                conn.execute(
                    insert(user_preferences).values(
                        key=key,
                        value=json.dumps(value),
                        updated_at=func.now()
                    )
                )
            conn.commit()
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve user preference with fallback to sensible defaults.
        
        This method fetches stored user preferences to personalize analysis and report
        generation. If no preference is found for the given key, returns the specified
        default value to ensure graceful degradation.
        
        Args:
            key: Preference identifier to retrieve
            default: Default value to return if preference doesn't exist
            
        Returns:
            The stored preference value (JSON-deserialized), or default if not found
            
        Example:
            audience = db.get_preference('default_audience', 'self')
            focus_areas = db.get_preference('focus_areas', ['technical'])
            tone = db.get_preference('tone_preference', 'professional')
        """
        self._ensure_initialized()
        with self.engine.connect() as conn:
            result = conn.execute(
                select(user_preferences.c.value)
                .where(user_preferences.c.key == key)
            )
            row = result.fetchone()
            if row:
                return json.loads(row.value)
        return default
    
    def save_wins(self, week_start: datetime, wins_data: Dict[str, Any]) -> int:
        """Save generated wins report for pattern learning and effectiveness tracking.
        
        This method stores complete wins analysis results to enable historical pattern
        recognition and continuous improvement of the agent's analysis quality. The stored
        data includes all discovered correlations, categorized achievements, and metadata
        for future learning and comparison.
        
        Args:
            week_start: Monday of the week being analyzed (normalized to midnight)
            wins_data: Complete wins analysis including correlations, categories, and summaries
            
        Returns:
            Integer ID of the saved wins record for future reference and feedback tracking
            
        Example:
            wins_data = {
                'summary': {'total_activities': 25, 'correlation_count': 8},
                'categories': {'technical': [...], 'leadership': [...]},
                'correlations': [{'confidence': 0.9, 'events': [...]}]
            }
            wins_id = db.save_wins(datetime(2024, 1, 15), wins_data)
        """
        self._ensure_initialized()
        with self.engine.connect() as conn:
            result = conn.execute(
                insert(wins_history).values(
                    week_start=week_start,
                    win_data_json=json.dumps(wins_data)
                )
            )
            conn.commit()
            return result.inserted_primary_key[0]
    
    def save_correlation(
        self,
        primary_source: str,
        primary_id: str,
        related_events: List[Dict[str, Any]],
        confidence: float,
        correlation_type: str
    ) -> int:
        """Save discovered cross-service correlation for reuse and pattern recognition.
        
        This method stores meaningful connections found between activities across different
        services (GitHub, Linear, Notion, Slack). These correlations are used to build
        a richer narrative of accomplishments and can be reused in future analysis to
        identify similar patterns.
        
        Args:
            primary_source: Source service of the primary event ('github', 'linear', 'notion', 'slack')
            primary_id: Unique identifier of the primary event within its service
            related_events: List of correlated events from other services
            confidence: Confidence score (0.0-1.0) indicating correlation strength
            correlation_type: Type of correlation ('temporal', 'keyword', 'semantic', 'causal')
            
        Returns:
            Integer ID of the saved correlation for tracking and future reference
            
        Example:
            related_events = [
                {'service': 'github', 'type': 'pull_request', 'id': '123', 'title': 'Add auth'},
                {'service': 'linear', 'type': 'issue', 'id': 'AUTH-45', 'title': 'Implement login'},
                {'service': 'notion', 'type': 'page', 'id': 'abc123', 'title': 'Auth Design Doc'}
            ]
            correlation_id = db.save_correlation(
                primary_source='github',
                primary_id='123',
                related_events=related_events,
                confidence=0.95,
                correlation_type='semantic'
            )
        """
        self._ensure_initialized()
        with self.engine.connect() as conn:
            result = conn.execute(
                insert(correlations).values(
                    primary_event_source=primary_source,
                    primary_event_id=primary_id,
                    related_events_json=json.dumps(related_events),
                    confidence_score=confidence,
                    correlation_type=correlation_type
                )
            )
            conn.commit()
            return result.inserted_primary_key[0]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics for monitoring and optimization.
        
        This method provides detailed insights into cache usage patterns, hit rates,
        and data freshness across all services and data types. Used for monitoring
        API usage efficiency and identifying opportunities for cache optimization.
        
        Returns:
            Dictionary containing cache statistics grouped by service and data type,
            including count, latest timestamp, and earliest timestamp for each combination
            
        Example return structure:
            {
                'github_prs': {
                    'count': 15,
                    'latest': datetime(2024, 1, 20, 14, 30),
                    'earliest': datetime(2024, 1, 15, 9, 15)
                },
                'linear_issues': {
                    'count': 8,
                    'latest': datetime(2024, 1, 19, 16, 45),
                    'earliest': datetime(2024, 1, 16, 11, 20)
                }
            }
        """
        self._ensure_initialized()
        with self.engine.connect() as conn:
            result = conn.execute(
                select(
                    raw_activity.c.source,
                    raw_activity.c.data_type,
                    func.count().label('count'),
                    func.max(raw_activity.c.timestamp).label('latest'),
                    func.min(raw_activity.c.timestamp).label('earliest')
                ).group_by(raw_activity.c.source, raw_activity.c.data_type)
            )
            
            stats = {}
            for row in result:
                key = f"{row.source}_{row.data_type}"
                stats[key] = {
                    "count": row.count,
                    "latest": row.latest,
                    "earliest": row.earliest
                }
            
            return stats
    
    def clear_cache(self, older_than_days: int = 7):
        """Clear old cached data to manage storage and maintain data freshness.
        
        This method removes cached API responses older than the specified threshold
        to prevent unlimited database growth while preserving recent data for
        correlation analysis and quick retrieval.
        
        Args:
            older_than_days: Remove cache entries older than this many days (default: 7)
            
        Example:
            # Clear cache older than 3 days
            db.clear_cache(older_than_days=3)
            
            # Use default 7-day retention
            db.clear_cache()
        """
        self._ensure_initialized()
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=older_than_days)
        
        with self.engine.connect() as conn:
            conn.execute(
                delete(raw_activity).where(raw_activity.c.timestamp < cutoff)
            )
            conn.commit()