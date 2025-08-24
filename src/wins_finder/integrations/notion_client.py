"""Notion integration client stub."""

from typing import Dict, Any, Optional
from datetime import datetime
from wins_finder.database.models import WinsDatabase


class NotionClient:
    """Stub Notion client for future implementation."""

    def __init__(self, db: Optional[WinsDatabase] = None):
        self.db = db or WinsDatabase()

    def test_connection(self, api_key: str) -> bool:
        return False  # Not implemented

    def get_activity(
        self, start_date: datetime, end_date: datetime, use_cache: bool = True
    ) -> Dict[str, Any]:
        return {"activities": [], "summary": {}, "from_cache": False}
