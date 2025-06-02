"""Progress operations for ORM database layer."""

import logging
from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError

from . import orm_models
from .orm_session import get_session
from .models import ProgressEntry
from ..core.exceptions import DatabaseError

log = logging.getLogger(__name__)


def log_progress(workspace_id: str, progress_data: ProgressEntry) -> ProgressEntry:
    """Logs a new progress entry."""
    try:
        with get_session(workspace_id) as session:
            orm_progress = orm_models.ProgressEntry(
                timestamp=progress_data.timestamp,
                status=progress_data.status,
                description=progress_data.description,
                parent_id=progress_data.parent_id
            )
            session.add(orm_progress)
            session.commit()
            
            progress_data.id = orm_progress.id
            return progress_data
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to log progress entry: {e}")


def get_progress(
    workspace_id: str,
    status_filter: Optional[str] = None,
    parent_id_filter: Optional[int] = None,
    limit: Optional[int] = None
) -> List[ProgressEntry]:
    """Retrieves progress entries, optionally filtered and limited."""
    try:
        with get_session(workspace_id) as session:
            query = session.query(orm_models.ProgressEntry)
            
            if status_filter:
                query = query.filter(orm_models.ProgressEntry.status == status_filter)
            if parent_id_filter is not None:
                query = query.filter(orm_models.ProgressEntry.parent_id == parent_id_filter)
            
            query = query.order_by(orm_models.ProgressEntry.timestamp.desc())
            
            if limit is not None and limit > 0:
                query = query.limit(limit)
            
            orm_progress = query.all()
            
            return [
                ProgressEntry(
                    id=p.id,
                    timestamp=p.timestamp,
                    status=p.status,
                    description=p.description,
                    parent_id=p.parent_id
                ) for p in orm_progress
            ]
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to retrieve progress entries: {e}")