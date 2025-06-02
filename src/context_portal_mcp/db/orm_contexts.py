"""Context operations for ORM database layer."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from . import orm_models
from .orm_session import get_session
from .models import ProductContext, ActiveContext, UpdateContextArgs
from ..core.exceptions import DatabaseError

log = logging.getLogger(__name__)


def get_latest_context_version(session: Session, history_model) -> int:
    """Retrieves the latest version number from a history table."""
    try:
        result = session.query(func.max(history_model.version)).scalar()
        return result if result is not None else 0
    except SQLAlchemyError as e:
        log.error(f"Error getting latest version: {e}")
        return 0


def add_context_history_entry(
    session: Session,
    history_model,
    version: int,
    content_dict: Dict[str, Any],
    change_source: Optional[str]
) -> None:
    """Adds an entry to the specified context history table."""
    try:
        history_entry = history_model(
            timestamp=datetime.utcnow(),
            version=version,
            content=content_dict,
            change_source=change_source
        )
        session.add(history_entry)
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to add history entry: {e}")


def get_product_context(workspace_id: str) -> ProductContext:
    """Retrieves the product context."""
    try:
        with get_session(workspace_id) as session:
            orm_context = session.query(orm_models.ProductContext).filter_by(id=1).first()
            if orm_context:
                return ProductContext(id=orm_context.id, content=orm_context.content)
            else:
                raise DatabaseError("Product context row not found.")
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to retrieve product context: {e}")


def update_product_context(workspace_id: str, update_args: UpdateContextArgs) -> None:
    """Updates the product context using either full content or a patch."""
    try:
        with get_session(workspace_id) as session:
            # Fetch current content to log to history
            orm_context = session.query(orm_models.ProductContext).filter_by(id=1).first()
            if not orm_context:
                raise DatabaseError("Product context row not found for updating.")
            
            current_content_dict = orm_context.content or {}
            
            # Determine new content
            if update_args.content is not None:
                new_final_content = update_args.content
            elif update_args.patch_content is not None:
                new_final_content = current_content_dict.copy()
                # Apply patch with __DELETE__ sentinel support
                for key, value in update_args.patch_content.items():
                    if value == "__DELETE__":
                        new_final_content.pop(key, None)
                    else:
                        new_final_content[key] = value
            else:
                raise ValueError("No content or patch_content provided for update.")
            
            # Log previous version to history
            latest_version = get_latest_context_version(session, orm_models.ProductContextHistory)
            new_version = latest_version + 1
            add_context_history_entry(
                session,
                orm_models.ProductContextHistory,
                new_version,
                current_content_dict,
                "update_product_context"
            )
            
            # Update the main product_context table
            orm_context.content = new_final_content
            session.commit()
            
    except (SQLAlchemyError, ValueError) as e:
        raise DatabaseError(f"Failed to update product_context: {e}")


def get_active_context(workspace_id: str) -> ActiveContext:
    """Retrieves the active context."""
    try:
        with get_session(workspace_id) as session:
            orm_context = session.query(orm_models.ActiveContext).filter_by(id=1).first()
            if orm_context:
                return ActiveContext(id=orm_context.id, content=orm_context.content)
            else:
                raise DatabaseError("Active context row not found.")
    except SQLAlchemyError as e:
        raise DatabaseError(f"Failed to retrieve active context: {e}")


def update_active_context(workspace_id: str, update_args: UpdateContextArgs) -> None:
    """Updates the active context using either full content or a patch."""
    try:
        with get_session(workspace_id) as session:
            # Fetch current content to log to history
            orm_context = session.query(orm_models.ActiveContext).filter_by(id=1).first()
            if not orm_context:
                raise DatabaseError("Active context row not found for updating.")
            
            current_content_dict = orm_context.content or {}
            
            # Determine new content
            if update_args.content is not None:
                new_final_content = update_args.content
            elif update_args.patch_content is not None:
                new_final_content = current_content_dict.copy()
                # Apply patch with __DELETE__ sentinel support
                for key, value in update_args.patch_content.items():
                    if value == "__DELETE__":
                        new_final_content.pop(key, None)
                    else:
                        new_final_content[key] = value
            else:
                raise ValueError("No content or patch_content provided for update.")
            
            # Log previous version to history
            latest_version = get_latest_context_version(session, orm_models.ActiveContextHistory)
            new_version = latest_version + 1
            add_context_history_entry(
                session,
                orm_models.ActiveContextHistory,
                new_version,
                current_content_dict,
                "update_active_context"
            )
            
            # Update the main active_context table
            orm_context.content = new_final_content
            session.commit()
            
    except (SQLAlchemyError, ValueError) as e:
        raise DatabaseError(f"Failed to update active context: {e}")