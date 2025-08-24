"""SQLAlchemy Core models for the Wins Finder MCP agent."""

from sqlalchemy import (
    MetaData, Table, Column, Integer, String, DateTime, Boolean, Float, Text,
    create_engine, select, insert, update, delete, func
)
from sqlalchemy.sql import text
from datetime import datetime
import json
from typing import Dict, List, Optional, Any


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
            # Use user data directory that's writable
            import os
            from pathlib import Path
            
            # Create user data directory
            try:
                if os.name == 'nt':  # Windows
                    data_dir = Path.home() / "AppData" / "Local" / "wins-finder"
                else:  # macOS/Linux
                    data_dir = Path.home() / ".local" / "share" / "wins-finder"
                
                data_dir.mkdir(parents=True, exist_ok=True)
                db_path = data_dir / "wins_finder.db"
                db_url = f"sqlite:///{db_path}"
            except (OSError, PermissionError):
                # Fallback to current directory if user data dir fails
                import tempfile
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
        """Cache API response data."""
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
        """Retrieve cached activity data if still fresh."""
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
        """Save user preference."""
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
        """Get user preference."""
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
        """Save generated wins for history."""
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
        """Save cross-service correlation."""
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
        """Get cache statistics for monitoring."""
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
        """Clear old cached data."""
        self._ensure_initialized()
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=older_than_days)
        
        with self.engine.connect() as conn:
            conn.execute(
                delete(raw_activity).where(raw_activity.c.timestamp < cutoff)
            )
            conn.commit()