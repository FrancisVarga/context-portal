"""Decision operations for ORM database layer."""

import logging
from typing import List, Optional
from sqlalchemy import text, func, Text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from . import orm_models
from .orm_session import get_session
from .db_config import get_database_config
from .models import Decision
from ..core.exceptions import DatabaseError

log = logging.getLogger(__name__)


def log_decision(workspace_id: str, decision_data: Decision) -> Decision:
    """Logs a new decision."""
    try:
        with get_session(workspace_id) as session:
            orm_decision = orm_models.Decision(
                timestamp=decision_data.timestamp,
                summary=decision_data.summary,
                rationale=decision_data.rationale,
                implementation_details=decision_data.implementation_details,
                tags=decision_data.tags
            )
            session.add(orm_decision)
            session.commit()
            
            # Return the decision with the new ID
            decision_data.id = orm_decision.id
            return decision_data
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to log decision: {e}")


def get_decisions(
    workspace_id: str,
    limit: Optional[int] = None,
    tags_filter_include_all: Optional[List[str]] = None,
    tags_filter_include_any: Optional[List[str]] = None
) -> List[Decision]:
    """Retrieves decisions, optionally limited, and filtered by tags."""
    try:
        with get_session(workspace_id) as session:
            query = session.query(orm_models.Decision).order_by(orm_models.Decision.timestamp.desc())
            
            if limit is not None and limit > 0:
                query = query.limit(limit)
            
            orm_decisions = query.all()
            
            # Convert to model objects
            decisions = [
                Decision(
                    id=d.id,
                    timestamp=d.timestamp,
                    summary=d.summary,
                    rationale=d.rationale,
                    implementation_details=d.implementation_details,
                    tags=d.tags
                ) for d in orm_decisions
            ]
            
            # Apply tag filtering in Python for compatibility
            if tags_filter_include_all:
                decisions = [
                    d for d in decisions 
                    if d.tags and all(tag in d.tags for tag in tags_filter_include_all)
                ]
            
            if tags_filter_include_any:
                decisions = [
                    d for d in decisions 
                    if d.tags and any(tag in d.tags for tag in tags_filter_include_any)
                ]
            
            return decisions
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to retrieve decisions: {e}")


def search_decisions_fts(workspace_id: str, query_term: str, limit: Optional[int] = 10) -> List[Decision]:
    """Searches decisions using FTS for the given query term."""
    config = get_database_config(workspace_id)
    
    try:
        with get_session(workspace_id) as session:
            if config.is_sqlite:
                # Use SQLite FTS5
                query = session.query(orm_models.Decision).from_statement(
                    text("""
                        SELECT d.id, d.timestamp, d.summary, d.rationale, d.implementation_details, d.tags
                        FROM decisions_fts f
                        JOIN decisions d ON f.rowid = d.id
                        WHERE f.decisions_fts MATCH :query_term ORDER BY rank
                        LIMIT :limit
                    """)
                ).params(query_term=query_term, limit=limit or 10)
                
            elif config.is_postgresql:
                # Use PostgreSQL full-text search
                query = session.query(orm_models.Decision).filter(
                    func.to_tsvector('english',
                        func.coalesce(orm_models.Decision.summary, '') + ' ' +
                        func.coalesce(orm_models.Decision.rationale, '') + ' ' +
                        func.coalesce(orm_models.Decision.implementation_details, '') + ' ' +
                        func.coalesce(orm_models.Decision.tags.cast(Text), '')
                    ).op('@@')(func.plainto_tsquery('english', query_term))
                ).order_by(
                    func.ts_rank(
                        func.to_tsvector('english',
                            func.coalesce(orm_models.Decision.summary, '') + ' ' +
                            func.coalesce(orm_models.Decision.rationale, '') + ' ' +
                            func.coalesce(orm_models.Decision.implementation_details, '') + ' ' +
                            func.coalesce(orm_models.Decision.tags.cast(Text), '')
                        ),
                        func.plainto_tsquery('english', query_term)
                    ).desc()
                ).limit(limit or 10)
            
            orm_decisions = query.all()
            
            return [
                Decision(
                    id=d.id,
                    timestamp=d.timestamp,
                    summary=d.summary,
                    rationale=d.rationale,
                    implementation_details=d.implementation_details,
                    tags=d.tags
                ) for d in orm_decisions
            ]
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed FTS search on decisions for term '{query_term}': {e}")


def delete_decision_by_id(workspace_id: str, decision_id: int) -> bool:
    """Deletes a decision by its ID. Returns True if deleted, False otherwise."""
    try:
        with get_session(workspace_id) as session:
            deleted_count = session.query(orm_models.Decision).filter_by(id=decision_id).delete()
            session.commit()
            return deleted_count > 0
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to delete decision with ID {decision_id}: {e}")