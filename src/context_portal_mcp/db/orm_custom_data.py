"""Custom data operations for ORM database layer."""

import logging
from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError

from . import orm_models
from .orm_session import get_session
from .models import CustomData
from ..core.exceptions import DatabaseError

log = logging.getLogger(__name__)


def log_custom_data(workspace_id: str, data: CustomData) -> CustomData:
    """Logs or updates a custom data entry."""
    try:
        with get_session(workspace_id) as session:
            # Check if entry exists (based on category + key uniqueness)
            existing = session.query(orm_models.CustomData).filter_by(
                category=data.category, key=data.key
            ).first()
            
            if existing:
                # Update existing
                existing.timestamp = data.timestamp
                existing.value = data.value
                data.id = existing.id
            else:
                # Create new
                orm_data = orm_models.CustomData(
                    timestamp=data.timestamp,
                    category=data.category,
                    key=data.key,
                    value=data.value
                )
                session.add(orm_data)
                session.flush()  # Get ID
                data.id = orm_data.id
            
            session.commit()
            return data
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to log custom data for '{data.category}/{data.key}': {e}")


def get_custom_data(
    workspace_id: str,
    category: Optional[str] = None,
    key: Optional[str] = None
) -> List[CustomData]:
    """Retrieves custom data entries, optionally filtered by category and/or key."""
    if key and not category:
        raise ValueError("Cannot filter by key without specifying a category.")
    
    try:
        with get_session(workspace_id) as session:
            query = session.query(orm_models.CustomData)
            
            if category:
                query = query.filter(orm_models.CustomData.category == category)
            if key:
                query = query.filter(orm_models.CustomData.key == key)
            
            query = query.order_by(
                orm_models.CustomData.category.asc(),
                orm_models.CustomData.key.asc()
            )
            
            orm_data = query.all()
            
            return [
                CustomData(
                    id=d.id,
                    timestamp=d.timestamp,
                    category=d.category,
                    key=d.key,
                    value=d.value
                ) for d in orm_data
            ]
            
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to retrieve custom data: {e}")