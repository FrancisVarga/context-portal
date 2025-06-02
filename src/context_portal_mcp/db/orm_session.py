"""Session management and engine creation for ORM database layer."""

import logging
from typing import Optional, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .db_config import get_database_config
from . import orm_models

log = logging.getLogger(__name__)

# Session management
_session_factories: Dict[str, sessionmaker] = {}
_engines: Dict[str, object] = {}


def get_engine(workspace_id: str, db_type: Optional[str] = None):
    """Get or create database engine for workspace."""
    config = get_database_config(workspace_id, db_type)
    key = f"{workspace_id}_{config.db_type}"
    
    if key not in _engines:
        url = config.get_connection_url()
        options = config.get_engine_options()
        _engines[key] = create_engine(url, **options)
        
        # Initialize database schema - import here to avoid circular import
        from .orm_init import init_database
        init_database(_engines[key], config)
    
    return _engines[key]


def get_session_factory(workspace_id: str, db_type: Optional[str] = None):
    """Get or create session factory for workspace."""
    config = get_database_config(workspace_id, db_type)
    key = f"{workspace_id}_{config.db_type}"
    
    if key not in _session_factories:
        engine = get_engine(workspace_id, db_type)
        _session_factories[key] = sessionmaker(bind=engine)
    
    return _session_factories[key]


def get_session(workspace_id: str, db_type: Optional[str] = None) -> Session:
    """Get database session for workspace."""
    session_factory = get_session_factory(workspace_id, db_type)
    return session_factory()


def close_all_connections():
    """Closes all active database connections."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _session_factories.clear()


def close_db_connection(workspace_id: str, db_type: Optional[str] = None):
    """Closes the database connection for the given workspace."""
    config = get_database_config(workspace_id, db_type)
    key = f"{workspace_id}_{config.db_type}"
    
    if key in _engines:
        _engines[key].dispose()
        del _engines[key]
    
    if key in _session_factories:
        del _session_factories[key]